1. 修正の確認
- サンプルの世代管理は妥当。ただし `App.tsx:App` の初期化effectと `useAnalysis.ts:useAnalysis` の組合せに退行があります。開発時のStrictModeで自動サンプル取得がcleanupにより中断され、`bootRef` が再実行を阻むため、`?sample=1` が「解析中」のままになります。
- `SettingsPanel.tsx:SettingsPanel`：下書き保持・リセットは改善。ただし解析中も編集でき、完了時の `[applied]` effectが、その間の追加入力を上書きします。
- `main.py:validation_error_handler`：NaNの422化は両ルートでテスト成功。
- ノイズ除去の順序、面積0の除外は修正どおり。ただし下記Highは残存。
- `format.ts:roomsToCsv, labelPoint`：数式対策・CRエスケープ・走査線追加に明らかな退行は確認せず。
- `RoomDetail.tsx:Chips`：button化は妥当。ただし辺の強調は依然ホバー専用で、開口チップはIDが空なので強調されません。
- `useAnalysis.ts:runWithin`：レスポンスから適用条件を取得する修正は妥当。

2. 提出前に直すべきHigh
- `analyzer.py:wall_intervals_on_edge`：クリップ後の短区間除去が残存。同じ100px壁でも、部屋辺を5pxずつに分割すると、tol=10で壁長が100→0pxになることを実行確認。元線分に基づくノイズ判定等が必要です。
- `analyzer.py:analyze`：非ゼロ面積の自己交差は警告後も部屋・合計・CSVに含まれます。不正形状の正常集計を防ぐには、拒否または集計除外が必要です。

指定のpytest：**38 passed**。tsc：**成功**。ファイル変更なし。フロントの動作評価は静的確認です。