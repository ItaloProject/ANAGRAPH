# 📊 ANAGRAPH — AI Trading Chart Analyzer

> Robô de análise gráfica de alto nível para EUR/USD na plataforma Deriv.
> Combina análise técnica multi-camada com inteligência adaptativa para trades de alta assertividade.

---

## 🧠 Engine de Análise (v3)

O ANAGRAPH utiliza um pipeline de 11 camadas de análise antes de abrir qualquer posição:

| Camada | Indicadores |
|--------|-------------|
| **1. Indicadores clássicos** | RSI, Stochastic, MACD, Bollinger Bands, EMA 9/21/50 |
| **2. Força de tendência** | ADX (mín. 22) — bloqueia mercado lateral |
| **3. Filtro de volatilidade** | ATR — bloqueia spikes de notícia (>2.5×) e mercado morto (<0.3×) |
| **4. Sessões de mercado** | London, NY, London+NY (premium) — bloqueia sessão asiática |
| **5. Multi-Timeframe (MTF)** | H4 macro + H1 confirmação + M15 entrada |
| **6. Price Action** | Pin Bar, Hammer, Engolfo, Shooting Star, Marubozu, Morning/Evening Star |
| **7. Market Structure** | Swing H/L, Break of Structure, Liquidity Sweep, HH/LL |
| **8. Divergência** | RSI divergência + MACD histograma divergência |
| **9. Fair Value Gap + Order Blocks** | Zonas de desequilíbrio institucional (ICT) |
| **10. Auto-ajuste adaptativo** | Ajusta thresholds automaticamente por win rate dos últimos 30 trades |
| **11. Backtesting walk-forward** | Valida parâmetros em histórico real antes de operar |

---

## 🛡️ Gestão de Risco

- Confiança mínima: **78%** (ajustável)
- Máx. losses consecutivos: **3** (para o bot automaticamente)
- Cooldown pós-loss: **5 minutos**
- Limite de perda diária: **R\$ 100** (para o bot ao atingir)
- Meta de lucro diária: **R\$ 150** (para o bot ao atingir)
- Auto-stop: o bot **para completamente** ao atingir qualquer limite

---

## 🚀 Stack

| Componente | Tecnologia |
|------------|------------|
| Backend    | Python 3.11 · FastAPI · uvicorn · WebSocket |
| Análise    | pandas · ta (technical analysis) · numpy |
| Frontend   | Quasar (Vue 3) · TypeScript · lightweight-charts |
| API        | Deriv WebSocket API (Rise/Fall contracts) |

---

## ⚙️ Instalação

### Backend

\\\ash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env         # preencha com suas credenciais Deriv
\\\

### Frontend

\\\ash
cd frontend
npm install
\\\

---

## ▶️ Como rodar

### Backend (porta 8001)

\\\ash
cd backend
venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
\\\

### Frontend (porta 9000)

\\\ash
cd frontend
npm run dev
\\\

Acesse: **http://localhost:9000**

---

## 📡 Principais endpoints da API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET    | /api/health | Status do servidor |
| POST   | /api/bot/start | Inicia o robô |
| POST   | /api/bot/stop | Para o robô |
| GET    | /api/bot/status | Snapshot completo |
| GET    | /api/bot/adaptive | Estado do auto-ajuste |
| GET    | /api/backtest/run | Roda backtest walk-forward |
| WS     | /ws | WebSocket para eventos em tempo real |

---

## 📱 Telas do Frontend

- **Dashboard** — visão geral com indicadores e sinais
- **Ao Vivo** — análise em tempo real, operações abertas e histórico
- **Gráfico** — candlestick com indicadores visuais
- **Sinais** — histórico de sinais gerados
- **Backtest** — simulação walk-forward com curva de equity
- **Config** — parâmetros do robô e gestão de risco

---

## 🔑 Credenciais Deriv

1. Acesse https://developers.deriv.com
2. Crie uma aplicação e obtenha o **App ID**
3. Gere um **API Token** com permissão de trading
4. Preencha o ackend/.env com as credenciais

---

## ⚠️ Aviso

Este software é para fins educacionais e de pesquisa. Trading envolve risco de perda de capital. Use apenas capital que você pode perder. Nunca opere com dinheiro que você não pode se dar ao luxo de perder.

---

*Powered by Deriv API · Built with FastAPI + Quasar*
