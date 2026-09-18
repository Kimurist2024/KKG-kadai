# フロントエンドのテスト

アプリの実装は `../../../frontend/src/`、Vitest のテストと検証用データはこのディレクトリに置きます。

| ファイル | 検証対象 |
|---|---|
| `apiProxy.test.ts` | Next.js の API プロキシ |
| `fixedSettings.test.tsx` | 課題の固定条件、即時解析、ファイル切替、壁警告・CSV |
| `geometryDisplay.test.tsx` | 穴・重複を含む図形と計算根拠の表示 |
| `planPan.test.tsx` | 図面のドラッグ移動 |
| `viewport.test.ts` | 選択部屋に合わせる表示範囲 |
| `selectionPerformance.test.tsx` | 通信なしの部屋選択、選択解除、フィット表示・パン位置の維持 |
| `format.test.ts` | 数値の表示書式 |
| `fixtures/sample-result.json` | 既存サンプルの解析結果 |
| `initialLoad.test.tsx` | 初期表示でサンプルを読み込まないこと、`?sample=1` とボタン押下でだけ読み込むこと |
| `overlapCheck.test.tsx` | 確認事項の「部屋の重複」の要約・並び順・表示と、図面での強調（hover と部屋チップ） |

`frontend/` から実行します。

```bash
npm test
npm run typecheck
npm run build
```

個別のテストは `npm test -- ../test/gpt-6/frontend/viewport.test.ts` のように指定できます。
Vitest の対象は `../../../frontend/vitest.config.ts`、型検査の対象は `../../../frontend/tsconfig.json` で設定しています。
コンポーネントテストは jsdom で実行し、実ブラウザでの表示確認とは区別します。

部分スクロールは `partialScroll.test.tsx` で検証します。実ブラウザのスクロール動作は jsdom では再現しません。
