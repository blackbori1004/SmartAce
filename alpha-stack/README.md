# Alpha Stack Starter (ACP + Polymarket + DEX)

초기자본 $1,000 기준으로 **리스크 낮은 데이터/알림형**부터 시작하는 스타터 킷.

## 0) 준비

```bash
cd ~/\.openclaw/workspace/alpha-stack
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 1) 환경변수

```bash
export ETH_RPC_URL="https://eth-mainnet.g.alchemy.com/v2/<KEY>"
# 선택: Base, Arbitrum
export BASE_RPC_URL="https://base-mainnet.g.alchemy.com/v2/<KEY>"
export ARB_RPC_URL="https://arb-mainnet.g.alchemy.com/v2/<KEY>"
```

## 2) RPC 체크

```bash
python scripts/check_rpc.py
```

## 3) Polymarket 실시간 스트림(시장 데이터)

```bash
python scripts/polymarket_ws.py
```

- 기본 채널: `market`
- 기본 엔드포인트: `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- 주문 실행은 없음. **데이터 수집 전용**.

## 4) DEX 가격 스프레드 모니터 (알림형)

```bash
python scripts/dex_quote_monitor.py --pair ETH/USDC --interval 8
```

- DexScreener 공용 API로 복수 DEX 가격 비교
- 체결은 없음. **기회 탐지**만 수행

## 5) 웹 대시보드 (추천)

```bash
# 보안 토큰 지정 (강력 권장)
export DASHBOARD_TOKEN="your-strong-token"
# 페어 변경 가능 (기본: WETH/USDC)
export DEX_PAIR="WETH/USDC"
python scripts/dashboard.py
```

브라우저에서 열기 (토큰 필수):

- Mac: `http://127.0.0.1:8788/?token=your-strong-token`
- Phone(같은 Wi-Fi): `http://<맥의로컬IP>:8788/?token=your-strong-token`

다른 Wi-Fi에서도 보려면(선택):

```bash
# cloudflared 설치 후
cloudflared tunnel --url http://127.0.0.1:8788
```

표시 항목:

- ETH RPC 연결/블록 높이
- DEX 스프레드
- Polymarket WS 연결 상태/메시지 카운트
- Paper Trading 시뮬레이션(PnL/승률/거래수)
- Hyperliquid 현황(계정가치/포지션)
- 실행 히스토리(최근 체결 기록)

## 6) Hyperliquid API 실행 엔진 (브라우저 클릭 대체)

```bash
# 상태 확인 (spot/perp)
python scripts/hyperliquid_bot.py status

# 주문 드라이런 (실행 안 함)
python scripts/hyperliquid_bot.py order --symbol BTC --side buy --usd 100 --leverage 2

# 실주문 1회 실행
python scripts/hyperliquid_bot.py order --symbol BTC --side buy --usd 100 --leverage 2 --execute

# 페이퍼 조건과 동일한 실거래 루프 시작
python -u scripts/live_trader.py
```

환경변수:

- `HYPERLIQUID_PRIVATE_KEY` (필수)
- `HL_ACCOUNT_ADDRESS` (선택: 다른 주소로 실행할 때)
- `HL_MAX_NOTIONAL_USD` (기본 100)
- `HL_MAX_DAILY_LOSS_PCT` (기본 3)
- `HL_MAX_SLIPPAGE` (기본 0.003)

Kill switch:

```bash
touch ~/.openclaw/workspace/.pi/hyperliquid.pause
```

(파일이 있으면 주문이 자동 차단됨)

## 7) 다음 단계 (내가 같이 붙어서 진행)

1. 알림 임계값 튜닝 (거짓신호 줄이기)
2. CSV 로그 누적
3. 7일 백테스트 리포트
4. 통과 전략만 소액 반자동 실행

## 리스크 규칙

- 실거래 전 최소 2주 시뮬레이션
- 1회 손실 1.5% / 일손실 3% 상한
- 출금/송금/주문권한 변경은 반드시 사용자 승인
