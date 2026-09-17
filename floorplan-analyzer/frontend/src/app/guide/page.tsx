import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "使い方 | 平面図 面積・壁面積 解析" };

/** 初めての利用者を JSON 入力から結果の確認へ案内するページ。 */
export default function GuidePage() {
  return (
    <main className="app usage-guide">
      <nav aria-label="解析画面への移動"><Link href="/">解析画面へ</Link></nav>
      <header>
        <h1>はじめての方へ：使い方</h1>
        <p>JSON を読み込むだけで、部屋ごとの床面積・周長・壁面積を確認できます。まずはサンプルで操作を試せます。</p>
      </header>
      <ol className="guide-steps">
        <li className="panel">
          <h2>1. JSON を選ぶ</h2>
          <p>「JSON ファイルを選択」（読込後は「別の JSON を選択」）を押すか、ファイルを選択枠へドラッグ＆ドロップします。選ぶと自動で解析が始まります。</p>
          <p>使えるのは、課題の「部屋・壁・ドアマスク.json」と同じ形式の JSON です。PDF や PNG・JPEG 画像は直接読み込めません。</p>
        </li>
        <li className="panel">
          <h2>2. 図面と結果を見る</h2>
          <p>図面には部屋・壁・ドア、結果表には各部屋の床面積・周長・壁面積が表示されます。「サンプル表示中」は同梱の図面を表示している目印です。</p>
          <p>計算条件は天井高 <strong>2.4 m</strong>、ドア高 <strong>2.0 m</strong>、縮尺 <strong>96.7 px ＝ 1.365 m</strong> に固定されています。入力は不要です。縮尺が異なる図面では実寸と一致しません。</p>
        </li>
        <li className="panel">
          <h2>3. 部屋を選んで根拠を確認する</h2>
          <p>表の行か図面の部屋をクリックすると、その部屋が強調表示されます。「算出根拠を見る」で計算式や辺ごとの壁・ドアの内訳を確認できます。</p>
          <p>壁のない区間は壁面積に含めず、ドア部分の面積を控除しています。結果を保存する場合は「CSV ダウンロード」を押します。</p>
        </li>
      </ol>
      <section className="panel" aria-labelledby="guide-checks">
        <h2 id="guide-checks">「要確認」が表示されたら</h2>
        <p>壁の情報が足りない、部屋の輪郭と壁が対応していないなどの可能性があります。確認事項の「対象を確認」から該当箇所へ移動し、元データと図面の壁・ドアを照合してください。壁面積が 0 m² でも「壁がない」とは限りません。</p>
      </section>
      <nav className="guide-actions" aria-label="解析を始める">
        <Link className="btn btn-primary btn-lg" href="/?sample=1">サンプルで試す</Link>
        <Link className="btn btn-lg" href="/?start=upload">JSON を選んで始める</Link>
      </nav>
    </main>
  );
}
