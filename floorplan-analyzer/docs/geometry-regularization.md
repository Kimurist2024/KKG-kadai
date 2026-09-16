# ソフト方向正則化と共有平面グラフ

## 狙い

部屋ごとに独立した輪郭の微小な傾きや境界のずれを減らし、同じ壁を表す辺に同一の `canonical_edge_id` を付与する。元の証拠を壊さないため機能はオプトインで、既定の `raw` 解析の数値と JSON 形式は変更しない。

## アルゴリズム

1. 長3 px以上の各辺を長さで重み付けし、`4θ` の循環平均から直交2方向を推定する。
2. 方向集中度0.80以上、7°以内のインライア重み75%以上、両軸の支持がそれぞれ15%以上の場合だけ補正する。
3. 各辺の法線方向の誤差を両端へ分配し、元座標へのデータ項を保ったまま8回反復する。頂点移動は最大3 pxに制限する。
4. `boundary_reference=centerline` の場合のみ、異なる部屋の3 px以内の頂点を完全連結条件で共有ノードにする。
5. 全境界を noding し、T字接合と部分重なりの端点で長辺を原子辺へ分割する。同じ原子辺を1本の正準辺に統合し、所有部屋IDを持つ平面グラフを作る。
6. 自己交差・無効ポリゴン、部屋ごとの面積変化0.5%超過のいずれかがあれば、全体を元座標へフォールバックする。

## API

- `geometry_mode=raw`（既定）: 元座標で計算する。
- `geometry_mode=regularized_shared&boundary_reference=centerline`: 補正と共有化を試みる。
- 補正を要求したレスポンスは `geometry_processing` に適用・見送り理由、最大移動量、共有辺数、正準ノードと辺を含む。

## 現在の限界

- 交差・T字接合・部分重なりは原子辺に分割するが、壁厚や構造的な接合種別までは推定しない。
- `inner_face` は壁厚により隣接部屋の輪郭が本来異なるため、方向補正だけ行い、部屋間の吸着は行わない。
- マンハッタン型でない図面、または支配方向が曖昧な図面は `raw_fallback` となる。
- このグラフは部屋境界の一貫性を表すもので、構造設計上の壁心・壁厚を認定するものではない。

## 研究上の根拠

本実装は論文の学習モデルを複製したものではなく、次の研究に共通する「局所結果を独立に測らず、幾何制約と全体の接続関係でベクトル化する」考え方を、説明可能な決定的アルゴリズムとして採用した。

- Liu et al., [Raster-to-Vector: Revisiting Floorplan Transformation](https://openaccess.thecvf.com/content_ICCV_2017/html/Liu_Raster-to-Vector_Revisiting_Floorplan_ICCV_2017_paper.html), ICCV 2017.
- Chen et al., [Floor-SP: Inverse CAD for Floorplans by Sequential Room-wise Shortest Path](https://openaccess.thecvf.com/content_ICCV_2019/html/Chen_Floor-SP_Inverse_CAD_for_Floorplans_by_Sequential_Room-Wise_Shortest_Path_ICCV_2019_paper.html), ICCV 2019.
- Chen et al., [HEAT: Holistic Edge Attention Transformer for Structured Reconstruction](https://openaccess.thecvf.com/content/CVPR2022/html/Chen_HEAT_Holistic_Edge_Attention_Transformer_for_Structured_Reconstruction_CVPR_2022_paper.html), CVPR 2022.
