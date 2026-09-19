# Vercel デプロイ記録

## 最新: 2026-09-19（feature/kimura 9cdc491、初期画面の作り直しと重複箇所の表示を反映）

- 公開 URL: https://floorplan-analyzer-taupe.vercel.app（別名 https://floorplan-analyzer-kimu4.vercel.app）
- Deployment: `dpl_E8hgRQNmCeKwDWgYwxvShtobjWUA`（READY / production）
- 固有 URL: https://floorplan-analyzer-acvwqgkxv-kimu4.vercel.app（Deployment Protection のため直接アクセスはログインが必要。公開 URL は不要）
- 実行: `floorplan-analyzer/` で `npx vercel@59 deploy --prod --scope kimu4 --yes`。作業ツリーは feature/kimura の 9cdc491 で未コミットの変更なし
- HTTP での確認（computer use は不使用。ブラウザでの画面操作は未確認）:
  - `/` 200 で、作り直した初期画面の文言（「JSON をドロップして面積を計算」「部屋ごとの床面積・周長・壁面積を求めます」「サンプルで試す」「入力形式について」）を含む。`/guide` 200
  - `/api/health` は `{"status":"ok"}`
  - `/api/analyze` に同梱サンプルを multipart 送信して 200。部屋 11・床面積合計 48.75 m²・壁面積合計 155.54 m²・重複を除いた床面積 48.58 m²
- 公開環境とローカル（macOS arm64 / Python 3.9）の応答を全フィールド比較: 構造・文字列・ID・警告文・配列順の相違は 0 件。数値 1,705 個のうち 26 個が末尾の桁だけ異なり、最大の相対差は 4.01e-14（前回 9c8b32b のときと同じ。実行環境の違いによるもの）
- 含まれる変更（前回 9c8b32b 以降でアプリに影響するもの）: 初期表示でサンプルを自動で読み込まない（#38）、確認事項の「部屋の重複」の一覧と図面の連動（#40）、重複の強調を形に沿った縁取りに変更（#41）、部屋名を押したときの強調表示（#42）、初期画面の作り直し（#43, #44）、tsconfig の設定修正（#47）。バックエンドの計算ロジックは前回から変更なし

## 2026-09-18 の記録（feature/kimura 9c8b32b、画像 AI の削除と初回解析の高速化を反映）

- 公開 URL: https://floorplan-analyzer-taupe.vercel.app（別名 https://floorplan-analyzer-kimu4.vercel.app）
- Deployment: `dpl_FVhwhathYJG9igkjmFQvGUgC3tDX`（READY / production）
- 固有 URL: https://floorplan-analyzer-8gv6rfa84-kimu4.vercel.app（Deployment Protection のため直接アクセスはログインが必要。公開 URL は不要）
- Inspector: https://vercel.com/kimu4/floorplan-analyzer/FVhwhathYJG9igkjmFQvGUgC3tDX
- 実行: `floorplan-analyzer/` で `npx vercel@59 deploy --prod --scope kimu4 --yes`（Vercel CLI 59.23.1）。作業ツリーは feature/kimura の 9c8b32b で未コミットの変更なし
- HTTP での確認（computer use は不使用。ブラウザでの画面操作は未確認）:
  - `/` 200、`/guide` 200 で今回の文言（「要確認」が出ていない部屋も確認対象に含める旨）を含む
  - `/api/health` は `{"status":"ok"}`。削除した画像 AI の `/api/recognize` は 404
  - `/api/analyze` に同梱サンプルを multipart 送信して 200（往復約 1.3 秒。コールドスタートを含む）。部屋 11・壁線 21・ドア線 9・警告 20 件（`room_overlap` / `unnamed_room`）でローカルと一致
- 公開環境とローカル（macOS arm64 / Python 3.9）の応答を全フィールド比較: 構造・文字列・ID・警告文・配列順はすべて一致。数値 1,705 個のうち 26 個が末尾の桁だけ異なり、最大の相対差は 4.01e-14（`summary.overlap_floor_area_m2`）。小数第 3 位で丸めると差は 0 個で、画面表示と CSV には影響しない。床面積合計は公開 48.75334707816534 / ローカル 48.75334707816535、壁面積合計は公開 155.53741974532744 / ローカル 155.53741974532747。実行環境（OS・CPU・Python・GEOS のビルド）の違いによる浮動小数点の末尾差で、ローカルでは変更前の凍結実装と現行の cold / warm / キャッシュ無効がすべて同じ値になることを確認済み
- 含まれる変更（前回 69c083f 以降でアプリに影響するもの）: 端点イベント走査による高速化（#14）、画像 AI 機能の削除（#28）、使い方ページの文言（#33）、初回解析の高速化（#35）。開発サーバー専用の `allowedDevOrigins`（#36）は本番ビルドに影響しない

## 2026-09-17 の記録（feature/kimura 69c083f、UI 改善サイクル 1〜2 を反映）

- 公開 URL: https://floorplan-analyzer-taupe.vercel.app（別名 https://floorplan-analyzer-kimu4.vercel.app）
- Deployment: `dpl_HxUt8omQi6FEbLD6NCiRoAa3SbSB`（READY / production）
- 固有 URL: https://floorplan-analyzer-7p96yldht-kimu4.vercel.app（Deployment Protection のため直接アクセスはログインが必要。公開 URL は不要）
- Inspector: https://vercel.com/kimu4/floorplan-analyzer/HxUt8omQi6FEbLD6NCiRoAa3SbSB
- 実行: `npx vercel@59 deploy --prod --scope kimu4 --yes`（Vercel CLI 59.20.0）
- HTTP での確認（computer use は不使用）: `/` 200 で新しい計算条件の説明文を含む、`/guide` 200 で書き直した使い方ページ、`/api/health` `{"status":"ok"}`、`/api/analyze` にサンプルを送信して 部屋 11・床面積合計 48.75 m²・壁面積合計 155.54 m²（ローカルと一致）
- 含まれる変更: 使い方ページの書き直し（#12）、見出し・条件の式の常時表示・壁なし長の強調・要確認バッジ・選択行・スクロール保持・ファイルバー・集計カードの序列・並べ替え 3 状態・表示名の復元・reduced-motion（UI 改善サイクル 1〜2）、幾何計算と表示コンポーネントの整理（#5）、空間検索の高速化（#11）

## 2026-09-15 の記録

本番デプロイの READY と、ログインなしの HTTP アクセス・サンプル解析を確認しました。

- 公開 URL: https://floorplan-analyzer-taupe.vercel.app
- 別名: https://floorplan-analyzer-kimu4.vercel.app
- Deployment: `dpl_7UhsuKcGq8gsvLQXRLwe4psNDnNy`
- 固有 URL: https://floorplan-analyzer-m2h08d0qv-kimu4.vercel.app
- Inspector: https://vercel.com/kimu4/floorplan-analyzer/7UhsuKcGq8gsvLQXRLwe4psNDnNy
- Vercel CLI 59.16.0 の deploy 結果: READY / production

扉投影の再利用、区間処理、STRtree、条件変更用の幾何キャッシュまで反映した版です。以前の更新では部屋選択時の表示処理を高速化し、部屋ホバー時の不透明度を80%・輪郭幅を3に強めています。[計測記録](selection-performance.md)。

## 配置

アプリ直下の `vercel.json` の Services 設定により Next.js と FastAPI を同じプロジェクトに配置。
`/api/*` は FastAPI の `app.main:app`、それ以外は Next.js が処理します。
この構成では外部 API_PROXY_TARGET は不要です。Docker/AWS/通常の Next.js 起動では従来の API プロキシを使用します。

## 以前の公開環境の確認結果（更新履歴）

- トップページ、静的 JS/CSS、サンプル JSON: HTTP 200
- `/api/health`: HTTP 200、`{"status":"ok"}`
- `/api/analyze` にサンプル JSON を multipart 送信: HTTP 200
- 部屋 11、壁線 21、ドア線 9
- 床面積合計: 48.75334707816534 m²
- 壁面積合計: 155.53741974532744 m²
- ローカルの既定条件での結果と一致
- `/api/ai/status`: `{"enabled":false}`

画像 AI は未設定です。利用には Vercel の環境変数 OPENAI_API_KEY / OPENAI_MODEL / AI_ACCESS_TOKEN を設定して再デプロイする必要があります。
実 AI の認識精度の検証はまだ行っていません。JSON 解析は AI キーなしで利用できます。
computer use は使わず、CLI と HTTP で検証しました。

## 更新時

アプリ直下で認証済み CLI から実行します。

```bash
npx vercel deploy --prod --scope kimu4
```

公開後に /api/health とサンプル解析を再確認してください。
以前 MCP の状態取得は403でしたが、CLI認証後に既存デプロイの成功を確認できました。

設定根拠: [Vercel Services](https://vercel.com/docs/services)、[Routing](https://vercel.com/docs/services/routing)。

「選択部屋に合わせる」は未選択時も押せるよう変更。押した後に図面・表から対象を選べます。表示切替時はスクロール位置をリセット。15テストと本番ビルド成功。computer use禁止のため実ブラウザでの目視は未実施。

フィット表示を縦横両軸の倍率計算に変更。画面高さ60%（最大560px）の枠に24pxの余白付きで収め、線幅・破線・文字サイズを画面pxに換算。全11部屋×3表示サイズの収まりと、追加ズーム・再フィットを含む17テスト成功。表示枠の縦横比にSVG viewBoxを一致させ、画像・輪郭の座標は共通のまま維持。

マウス左ドラッグで図面を上下左右に移動可能。5px未満の動きはクリックとして扱い、ドラッグ後の誤選択を抑制。SVGだけでイベントを処理し、スクロールバー・ホイール・タッチの標準操作を維持。19テスト・本番ビルド成功、実ブラウザ操作は未実施。

200%時の揺れ対策: ResizeObserverの幅更新からスクロール・倍率リセットを分離。scrollbar-gutterで幅を安定化し、overflow-anchorとスクロール連鎖を無効化。マウス押下時の標準選択/フォーカスによるスクロールを防ぎ、パン座標を範囲内に制限。200%時の幅変更と上下端の回帰テストを追加し21テスト・ビルド成功。実ブラウザでの揺れの再現・目視検証は未実施。

穴・部屋重複・扉の切れ目の拡張を公開。backend86件/frontend22件・本番ビルド成功。公開APIで元サンプルと人工デモのレスポンス全項目をローカル結果と照合（数値許容1e-10）。元サンプル床48.75334707816534m²・壁155.53741974532744m²維持、重複除外床48.576019852317955m²。詳細は [領域の拡張](geometry-upgrade.md)。

## 2026-09-15 アルゴリズム高速化

Next.js本番ビルド・TypeScriptチェック成功。バックエンド126件、フロントエンド22件のテスト成功。4段階の計測結果は[性能検証](validation/algorithm-performance/report.md)。

公開トップ・healthはHTTP200、サンプルと穴・扉切れ目デモを既定・高さ変更・縮尺変更の3条件で解析し全6件HTTP200。レスポンス全項目を凍結した変更前実装のローカル結果と比較。文字列・ID・配列順序は一致、数値最大絶対差は5.684341886080802e-14（辺長px）、デモは差0。ローカルPython3.9と本番Python3.12の異なる実行環境間の比較であり、環境差が原因かは分離検証していません。許容差abs1e-10/rel1e-12以内です。[生データ](validation/algorithm-performance/production-check.json)。

キャッシュは各プロセス内で最大8件・16MiB・5分。別インスタンスや期限切れでは再計算します。公開APIの通信時間やコールドスタート短縮を保証する測定ではありません。computer useは使用していません。
