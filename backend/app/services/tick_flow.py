"""
TickFlowAnalyzer — "sente o mercado" a partir do fluxo de ticks em tempo real.

Métricas computadas:
  velocity   — ticks por segundo (atividade do mercado)
  momentum   — variação de preço nas últimas N ticks (direção do fluxo)
  imbalance  — % de ticks de alta (≈ pressão compradora vs vendedora)
  smoothness — quão suave é o movimento (alta = tendência; baixa = ruído)

Essas métricas adicionam pontuação ao buy_score/sell_score do analyzer,
permitindo que o bot "sinta" aceleração de preço e pressão direcional
antes de entrar numa operação.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from time import time


@dataclass
class FlowState:
    velocity:   float = 0.0   # ticks/segundo
    momentum:   float = 0.0   # variação % nas últimas ticks
    imbalance:  float = 0.5   # 0=todo sell, 1=todo buy
    smoothness: float = 0.0   # 0=caótico, 1=suave
    buy_pts:    int   = 0
    sell_pts:   int   = 0
    reasons:    list  = None

    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []


class TickFlowAnalyzer:
    """
    Mantém um buffer circular dos últimos N ticks e computa métricas de fluxo.
    Leve o suficiente para rodar a cada tick sem afetar performance.
    """

    def __init__(self, buffer_size: int = 200):
        self._prices: deque[float] = deque(maxlen=buffer_size)
        self._times:  deque[float] = deque(maxlen=buffer_size)

    def push(self, price: float, epoch: float | None = None):
        self._prices.append(price)
        self._times.append(epoch if epoch is not None else time())

    def analyze(self, window: int = 60) -> FlowState:
        """
        Analisa os últimos `window` ticks e retorna FlowState com pontuação.
        Retorna estado neutro se dados insuficientes.
        """
        if len(self._prices) < max(20, window // 2):
            return FlowState()

        prices = list(self._prices)[-window:]
        times  = list(self._times)[-window:]
        n = len(prices)

        # ── Velocity (ticks por segundo) ─────────────────────────────────
        time_span = times[-1] - times[0]
        velocity  = n / time_span if time_span > 0 else 0.0

        # ── Momentum (variação % sobre o período) ────────────────────────
        p0       = prices[0]
        momentum = (prices[-1] - p0) / p0 * 100 if p0 != 0 else 0.0

        # ── Imbalance (% de ticks de alta) ───────────────────────────────
        up_ticks  = sum(1 for i in range(1, n) if prices[i] >= prices[i - 1])
        imbalance = up_ticks / (n - 1) if n > 1 else 0.5

        # ── Smoothness (média / desvio dos deltas = quanto o movimento é limpo) ─
        deltas   = [prices[i] - prices[i - 1] for i in range(1, n)]
        if deltas:
            mean_d = sum(deltas) / len(deltas)
            std_d  = (sum((d - mean_d) ** 2 for d in deltas) / len(deltas)) ** 0.5
            smoothness = abs(mean_d) / (std_d + 1e-10)
            smoothness = min(1.0, smoothness / 3.0)   # normaliza 0-1
        else:
            smoothness = 0.0

        buy_pts  = 0
        sell_pts = 0
        reasons: list[str] = []

        # ── Scoring ───────────────────────────────────────────────────────

        # Momentum forte de alta
        if momentum > 0.03 and imbalance > 0.60:
            buy_pts += 2
            reasons.append(f"Fluxo comprador ({momentum:+.3f}%)")
        elif momentum > 0.015:
            buy_pts += 1

        # Momentum forte de baixa
        if momentum < -0.03 and imbalance < 0.40:
            sell_pts += 2
            reasons.append(f"Fluxo vendedor ({momentum:+.3f}%)")
        elif momentum < -0.015:
            sell_pts += 1

        # Movimento suave e direcional (tendência limpa)
        if smoothness > 0.5:
            if momentum > 0:
                buy_pts += 1
                reasons.append(f"Tendência limpa (smooth={smoothness:.2f})")
            elif momentum < 0:
                sell_pts += 1
                reasons.append(f"Tendência limpa (smooth={smoothness:.2f})")

        # Desequilíbrio extremo de pressão
        if imbalance > 0.72:
            buy_pts += 1
            reasons.append(f"Pressão compradora ({imbalance:.0%} ticks up)")
        elif imbalance < 0.28:
            sell_pts += 1
            reasons.append(f"Pressão vendedora ({imbalance:.0%} ticks up)")

        # Alta velocidade + direção → confirma impulso
        if velocity > 1.5 and momentum > 0.02:
            buy_pts += 1
            reasons.append(f"Impulso comprador rápido ({velocity:.1f} tk/s)")
        elif velocity > 1.5 and momentum < -0.02:
            sell_pts += 1
            reasons.append(f"Impulso vendedor rápido ({velocity:.1f} tk/s)")

        return FlowState(
            velocity   = round(velocity, 2),
            momentum   = round(momentum, 4),
            imbalance  = round(imbalance, 3),
            smoothness = round(smoothness, 3),
            buy_pts    = buy_pts,
            sell_pts   = sell_pts,
            reasons    = reasons,
        )
