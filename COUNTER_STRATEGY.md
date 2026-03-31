# ToolRank v17: Trust Infrastructure Counter-Attack

## 概要

「Agent Trust Cloud」批評が指摘した5つの攻撃ベクトルすべてに対し、
具体的なコードとシステム設計で先手を打つ。

**戦略の核心:**
> ToolRankが「評価サイト」のままだと負ける。
> ToolRankを「信頼インフラ」に変える。今日、このコードで。

---

## 攻撃ベクトル → 対抗コード マッピング

### 1. 「Runtime-first 評価」攻撃
**脅威:** 「静的スコアは綺麗だけど、実際にagentが失敗してるよね？」
**対抗:** `scripts/selection_tournament.py`
- Claude Sonnet 100ラウンドトーナメント
- 4ツール同時提示 → LLMが最適ツール選択
- selection_rate をDB保存、サーバー詳細ページに表示
- Pro機能（コスト管理）

**なぜ効くか:** Layer 2を先に出荷すれば「static-only」批判は成立しない。
競合が「runtime-first」を謳う前に、ToolRankが実データを持つ。

---

### 2. 「配布統合」攻撃
**脅威:** 「スコアがあっても、流通に効かなければただの読み物」
**対抗:**
- `src/lib/trust-api.ts` — Trust Status API コア
- `src/pages/api/trust-status/[id].json.ts` — 個別サーバーの信頼プロファイル
- `src/pages/api/trusted-list.json.ts` — カテゴリ別信頼リスト
- `src/pages/api/trust-badge/[id].svg.ts` — 埋め込みバッジ
- `docs/distribution-api.md` — レジストリ統合ドキュメント

**なぜ効くか:** MCP.so / Official Registry / Smithery が
「ToolRank Verified」をそのまま表示できるAPIを提供する。
スコアが流通に接続された瞬間、インフラになる。

---

### 3. 「Clean Index」攻撃
**脅威:** 「ランキングに重複・test・forkが残っている」
**対抗:** `scripts/canonical_index.py`
- 30+パターンでtest/tutorial検出
- 説明文類似度 + ツール署名でduplicate検出
- GitHub API でfork判定 + maintenance status
- is_canonical / canonical_id / is_test / is_fork カラム追加
- 「うちはスコアの前にindexを綺麗にしています」と言える

**なぜ効くか:** clean index は信頼の土台。
汚いランキングへの批判を根本から除去する。

---

### 4. 「CI/CD 埋め込み」攻撃
**脅威:** 「評価を見る」ではなく「このゲートを通らないと出荷できない」
**対抗:**
- `.github/workflows/toolrank-gate-action.yml` — 3段階ゲート
- `docs/ci-cd-gates.md` — 実装ドキュメント

**3段階:**
| ゲート | タイミング | チェック |
|--------|-----------|---------|
| Pre-merge | PR時 | Spec品質 ≥ 閾値、エラー0 |
| Pre-release | リリースタグ時 | Spec + Selection win rate ≥ 閾値 |
| Post-deploy | デプロイ後 | Trust level ≥ 1、退行なし |

**なぜ効くか:** 「たまに見る評価サイト」→「毎日のCIで通るゲート」
開発者が毎日触れる場所にToolRankが組み込まれる。

---

### 5. 「認証を市場シグナルに」攻撃
**脅威:** 「バッジは自己申告。調達・導入で使えるシグナルではない」
**対抗:**
- `src/components/TrustTiers.astro` — 3層認証UI
- `src/components/TrustDashboard.astro` — 「何がtrustをブロックしているか」ダッシュボード
- `src/pages/trust/[id]/audit.astro` — 監査ログページ
- `supabase/migrations/001_trust_infrastructure.sql` — 全DB基盤

**認証体系:**
| Tier | 要件 | 失効条件 | 更新 |
|------|------|---------|------|
| Spec Verified | Score ≥ 85 | スコア低下 | 週次自動 |
| Selection Verified | Win Rate ≥ 70% | 60%未満に低下 | 月次 |
| Runtime Verified | 成功率 ≥ 90% | 持続的失敗 | 常時監視 |

**なぜ効くか:** 各tierに「要件・失効条件・監査ログ」がある。
自己申告バッジではなく、検証可能な制度。

---

## 新規ファイル一覧 (13ファイル)

```
supabase/migrations/001_trust_infrastructure.sql   ← DB基盤（6テーブル）
scripts/selection_tournament.py                     ← Layer 2 トーナメント
scripts/canonical_index.py                          ← Clean Index構築
src/lib/trust-api.ts                                ← Trust API コア
src/pages/api/trust-status/[id].json.ts             ← 個別Trust Profile API
src/pages/api/trusted-list.json.ts                  ← カテゴリ別Trusted List API
src/pages/api/trust-badge/[id].svg.ts               ← SVGバッジAPI
src/components/TrustTiers.astro                     ← 3層認証コンポーネント
src/components/TrustDashboard.astro                 ← Trustダッシュボード
src/pages/trust/[id]/audit.astro                    ← 監査ログページ
.github/workflows/toolrank-gate-action.yml          ← 3段階CIゲート
docs/ci-cd-gates.md                                 ← CIドキュメント
docs/distribution-api.md                            ← 配布統合ドキュメント
```

---

## 統合手順

1. **DB**: `001_trust_infrastructure.sql` を Supabase で実行
2. **Canonical Index**: `python canonical_index.py --scan --dry-run` で確認後 `--apply`
3. **Selection Tournament**: `python selection_tournament.py --category filesystem --rounds 100 --dry-run`
4. **API / Components**: 既存v16のsrc/に上書きコピー
5. **GitHub Action**: v2としてpush + Marketplace更新
6. **ドキュメント**: docs/ を site に統合

---

## 批評文書への回答（一言）

> 「ToolRankを潰すなら、より良いToolRankは作らない。
>   ToolRankを必要な部品にしてしまう、より大きな信頼インフラを作る。」

**回答:**
ToolRank自体が信頼インフラになれば、この攻撃ベクトルは消える。
v17はそのための設計図であり、実装そのものである。
