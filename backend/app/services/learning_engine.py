"""
LearningEngine — aprende com o histórico de trades para ajustar confiança dos sinais.

Funcionamento:
  1. Cada sinal operado (BUY/SELL) é salvo no SQLite com todos os indicadores
  2. Quando o trade fecha (WIN/LOSS), o resultado é registrado
  3. A cada 5 trades fechados, re-treina regressão logística nos últimos 500
  4. O modelo ajusta a confiança do próximo sinal com base em padrões similares
     que historicamente ganharam ou perderam

Banco: backend/data/anagraph.db (criado automaticamente)
Sem dependência de sklearn — usa NumPy puro.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "anagraph.db"

# Features usadas pelo modelo (ordem fixa)
FEATURE_NAMES = [
    "rsi", "macd_hist", "adx", "atr_ratio",
    "buy_score", "sell_score",
    "patterns_count", "divergences_count",
    "bb_pos",
]


class LearningEngine:
    """
    Motor de aprendizado online com regressão logística treinada em CPU.
    Thread-safe para uso em asyncio (operações síncronas em executor ou lock simples).
    """

    def __init__(self, db_path: Path = DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path    = str(db_path)
        self._weights: Optional[np.ndarray] = None
        self._mean: Optional[np.ndarray]    = None
        self._std:  Optional[np.ndarray]    = None
        self._sample_count = 0
        self._retrain_every = 5   # re-treina a cada N trades fechados
        self._closed_since_train = 0
        self._init_db()
        self._load_and_train()

    # ── Setup ─────────────────────────────────────────────────────────────────

    def _init_db(self):
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signal_history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp     TEXT    NOT NULL,
                signal        TEXT    NOT NULL,
                confidence    REAL,
                rsi           REAL,
                macd_hist     REAL,
                adx           REAL,
                atr_ratio     REAL,
                buy_score     INTEGER,
                sell_score    INTEGER,
                patterns_count   INTEGER,
                divergences_count INTEGER,
                bb_pos        REAL,
                h1_bias       TEXT,
                h4_bias       TEXT,
                session       TEXT,
                outcome       TEXT,
                contract_id   INTEGER,
                win_prob      REAL
            )
        """)
        conn.commit()
        conn.close()

    # ── Public API ────────────────────────────────────────────────────────────

    def record_signal(self, signal_data: dict, contract_id: Optional[int] = None) -> int:
        """Salva sinal no banco. Retorna o ID da linha para atualizar outcome depois."""
        bb_upper = signal_data.get("bb_upper", 0)
        bb_lower = signal_data.get("bb_lower", 0)
        price    = signal_data.get("price", 0)
        bb_width = bb_upper - bb_lower
        bb_pos   = (price - bb_lower) / bb_width if bb_width > 0 else 0.5

        macd_hist = (
            signal_data.get("macd", 0) - signal_data.get("macd_signal", 0)
        )

        features = self._extract_features({
            **signal_data,
            "macd_hist": macd_hist,
            "bb_pos":    bb_pos,
            "patterns_count":    len(signal_data.get("patterns", [])),
            "divergences_count": len(signal_data.get("divergences", [])),
        })
        win_prob = self._predict(features)

        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        cur  = conn.execute("""
            INSERT INTO signal_history
            (timestamp, signal, confidence, rsi, macd_hist, adx, atr_ratio,
             buy_score, sell_score, patterns_count, divergences_count, bb_pos,
             h1_bias, h4_bias, session, outcome, contract_id, win_prob)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,?,?)
        """, (
            datetime.now().isoformat(),
            signal_data.get("signal", "WAIT"),
            signal_data.get("confidence", 0),
            signal_data.get("rsi", 50),
            macd_hist,
            signal_data.get("adx", 0),
            signal_data.get("atr_ratio", 1),
            signal_data.get("buy_score", 0),
            signal_data.get("sell_score", 0),
            len(signal_data.get("patterns", [])),
            len(signal_data.get("divergences", [])),
            bb_pos,
            signal_data.get("h1_bias", "NEUTRAL"),
            signal_data.get("h4_bias", "NEUTRAL"),
            signal_data.get("session", ""),
            contract_id,
            win_prob,
        ))
        row_id = cur.lastrowid
        conn.commit()
        conn.close()
        return row_id

    def record_outcome(self, contract_id: int, outcome: str):
        """Registra WIN ou LOSS para um sinal já salvo e re-treina se necessário."""
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute(
            "UPDATE signal_history SET outcome=? WHERE contract_id=?",
            (outcome, contract_id),
        )
        conn.commit()
        conn.close()

        self._closed_since_train += 1
        if self._closed_since_train >= self._retrain_every:
            self._load_and_train()
            self._closed_since_train = 0

    def adjust_confidence(self, signal_data: dict, base_confidence: float) -> tuple[float, str]:
        """
        Retorna (adjusted_confidence, reason).
        Boost se modelo prediz alta probabilidade de ganho.
        Penalidade se modelo prediz baixa probabilidade.
        Neutro se ainda sem dados suficientes.
        """
        if self._weights is None:
            return base_confidence, ""

        bb_upper = signal_data.get("bb_upper", 0)
        bb_lower = signal_data.get("bb_lower", 0)
        price    = signal_data.get("price", 0)
        bb_width = bb_upper - bb_lower
        bb_pos   = (price - bb_lower) / bb_width if bb_width > 0 else 0.5

        features = self._extract_features({
            **signal_data,
            "macd_hist": signal_data.get("macd", 0) - signal_data.get("macd_signal", 0),
            "bb_pos":    bb_pos,
            "patterns_count":    len(signal_data.get("patterns", [])),
            "divergences_count": len(signal_data.get("divergences", [])),
        })
        prob = self._predict(features)

        if prob >= 0.70:
            adj = min(97.0, base_confidence + 6.0)
            return adj, f"[IA +6 WP={prob:.0%}]"
        elif prob >= 0.60:
            adj = min(97.0, base_confidence + 3.0)
            return adj, f"[IA +3 WP={prob:.0%}]"
        elif prob <= 0.35:
            adj = max(0.0, base_confidence - 12.0)
            return adj, f"[IA -12 WP={prob:.0%}]"
        elif prob <= 0.45:
            adj = max(0.0, base_confidence - 6.0)
            return adj, f"[IA -6 WP={prob:.0%}]"

        return base_confidence, f"[IA ={prob:.0%}]"

    def stats(self) -> dict:
        try:
            conn  = sqlite3.connect(self._db_path, check_same_thread=False)
            total = conn.execute(
                "SELECT COUNT(*) FROM signal_history WHERE outcome IS NOT NULL"
            ).fetchone()[0]
            wins  = conn.execute(
                "SELECT COUNT(*) FROM signal_history WHERE outcome='WIN'"
            ).fetchone()[0]
            conn.close()
            return {
                "total_recorded": total,
                "win_rate":       round(wins / total * 100, 1) if total else 0.0,
                "model_trained":  self._weights is not None,
                "sample_count":   self._sample_count,
            }
        except Exception:
            return {"total_recorded": 0, "win_rate": 0.0, "model_trained": False}

    # ── Training ──────────────────────────────────────────────────────────────

    def _load_and_train(self):
        try:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            rows = conn.execute("""
                SELECT rsi, macd_hist, adx, atr_ratio,
                       buy_score, sell_score,
                       patterns_count, divergences_count, bb_pos,
                       outcome
                FROM signal_history
                WHERE outcome IS NOT NULL AND signal != 'WAIT'
                ORDER BY id DESC LIMIT 500
            """).fetchall()
            conn.close()

            if len(rows) < 20:
                logger.info(f"[Learning] {len(rows)} amostras — treinamento adiado (mín 20)")
                return

            X = np.array([list(r[:9]) for r in rows], dtype=float)
            y = np.array([1 if r[9] == "WIN" else 0 for r in rows])

            self._mean = X.mean(axis=0)
            self._std  = X.std(axis=0) + 1e-8
            X_norm     = (X - self._mean) / self._std

            self._weights      = self._fit_logistic(X_norm, y)
            self._sample_count = len(rows)

            wr = y.mean() * 100
            logger.info(
                f"[Learning] Treinado em {len(rows)} amostras | WR histórico={wr:.1f}%"
            )
        except Exception as e:
            logger.error(f"[Learning] Falha no treinamento: {e}")

    @staticmethod
    def _fit_logistic(
        X: np.ndarray,
        y: np.ndarray,
        lr: float = 0.05,
        epochs: int = 300,
        l2: float = 0.01,
    ) -> np.ndarray:
        """Regressão logística via gradiente descendente com regularização L2."""
        n, d = X.shape
        w    = np.zeros(d + 1)
        Xb   = np.c_[np.ones(n), X]

        for _ in range(epochs):
            logits = Xb @ w
            pred   = 1.0 / (1.0 + np.exp(-np.clip(logits, -10, 10)))
            error  = pred - y
            grad   = Xb.T @ error / n
            # L2 regularização (não penaliza bias)
            reg       = l2 * w
            reg[0]    = 0.0
            w        -= lr * (grad + reg)

        return w

    def _predict(self, features: np.ndarray) -> float:
        """Retorna probabilidade de WIN (0-1)."""
        if self._weights is None or self._mean is None:
            return 0.5
        try:
            fn = (features - self._mean) / self._std
            fb = np.r_[1.0, fn]
            logit = float(fb @ self._weights)
            return float(1.0 / (1.0 + np.exp(-np.clip(logit, -10, 10))))
        except Exception:
            return 0.5

    @staticmethod
    def _extract_features(data: dict) -> np.ndarray:
        return np.array([
            data.get("rsi",              50.0),
            data.get("macd_hist",         0.0),
            data.get("adx",               0.0),
            data.get("atr_ratio",         1.0),
            data.get("buy_score",         0),
            data.get("sell_score",        0),
            data.get("patterns_count",    0),
            data.get("divergences_count", 0),
            data.get("bb_pos",            0.5),
        ], dtype=float)
