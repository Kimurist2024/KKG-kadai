import Link from "next/link";
import type { Metadata } from "next";
import { DOOR_COLOR, OPENING_COLOR, SELECT_COLOR, WALL_INTERVAL_COLOR } from "../../components/plan/colors";

export const metadata: Metadata = { title: "使い方 | 平面図 面積・壁面積 解析" };

/** 初めての利用者を JSON 入力から結果の確認へ案内するページ。 */
export default function GuidePage() {
  return (
    <main className="app usage-guide">
      <nav aria-label="解析画面への移動"><Link href="/">解析画面へ</Link></nav>
      <header>
        <h1>はじめての方へ：使い方</h1>
        <p>JSON を読み込むと、部屋ごとの床面積と壁面積が図面と表になって出てきます。解析画面で「サンプルで試す」を押すと同梱のサンプル図面を読み込めるので、ファイルを用意する前でも操作を試せます。天井高や縮尺などを入力する項目はありません。</p>
      </header>
      <section className="guide-hero panel" aria-labelledby="guide-hero-heading">
        <h2 id="guide-hero-heading">まず 1 分で結果を見る</h2>
        <nav className="guide-hero-actions" aria-label="いますぐ試す">
          <div className="guide-hero-item">
            <Link className="btn btn-primary btn-lg" href="/?sample=1" aria-label="サンプルで試す：同梱の図面をすぐ開く">サンプルで試す</Link>
            <p className="small muted">押すと解析画面が開き、同梱の図面 sample_mask.json が自動で解析されます。</p>
          </div>
          <div className="guide-hero-item">
            <Link className="btn btn-lg" href="/?start=upload" aria-label="JSON を選んで始める：自分のファイルを選ぶ">JSON を選んで始める</Link>
            <p className="small muted">押すと、サンプルを読み込まず、図面や結果表の代わりに大きなファイル選択枠が開きます。</p>
          </div>
        </nav>
        <p className="small muted">下の 3 ステップは、その画面で見えるものの説明です。</p>
        <p className="small muted">解析画面の見出し下の「はじめての方へ：使い方を見る」でこのページに戻れます（別タブで開いておくと便利です）。</p>
      </section>
      <section className="guide-flow panel" aria-labelledby="guide-flow-heading">
        <h2 id="guide-flow-heading">解析画面の並び</h2>
        <p>解析画面は上からこの順に並んでいます。右の番号は下の 3 ステップに対応します。</p>
        <div className="guide-flow-list">
          <div className="guide-flow-row"><span className="guide-flow-text">見出しと集計カード（「部屋数」「床面積 合計（部屋別の合算）」「壁面積 合計（内壁・両面計上）」）</span><span className="guide-num" role="img" aria-label="ステップ 2">2</span></div>
          <div className="guide-flow-row"><span className="guide-flow-text">ファイルバー（ファイル名・「サンプル表示中」・「別の JSON を選択」）</span><span className="guide-num" role="img" aria-label="ステップ 1">1</span></div>
          <div className="guide-flow-row"><span className="guide-flow-text">「課題指定の計算条件（固定）」のチップと、「解析中…」などのお知らせ</span><span className="guide-num" role="img" aria-label="ステップ 1">1</span></div>
          <div className="guide-flow-row"><span className="guide-flow-text">図面（表示レイヤー・「全体」「選択部屋に合わせる」「＋」「−」・凡例。警告があるときは「解析結果の確認事項」もここに出ます）</span><span className="guide-num" role="img" aria-label="ステップ 3">3</span></div>
          <div className="guide-flow-row"><span className="guide-flow-text">結果表（部屋ごとの床面積・周長・壁面積、「CSV ダウンロード」）</span><span className="guide-num" role="img" aria-label="ステップ 2">2</span></div>
          <div className="guide-flow-row"><span className="guide-flow-text">算出根拠パネル（部屋を選ぶと下に現れます）</span><span className="guide-num" role="img" aria-label="ステップ 3">3</span></div>
        </div>
        <p className="small muted">幅の広い画面では図面と結果表が左右に並び、狭い画面では図面の下に結果表が来ます。</p>
      </section>
      <ol className="guide-steps">
        <li className="panel" id="step-1">
          <h2><span className="guide-num">1</span>開くだけで結果が出ます</h2>
          <dl className="guide-pair">
            <dt>やること</dt>
            <dd>自分の JSON があれば「JSON を選んで始める」→ 大きな枠の「JSON ファイルを選択」（結果表示中は上部ファイルバーの「別の JSON を選択」）で選びます。サンプルは上の「サンプルで試す」を押します。解析画面をそのまま開いた場合も同じです。</dd>
            <dt>画面に出るもの</dt>
            <dd>「解析中…」のあと、図面と結果表が現れ、数秒間「結果を更新しました」と出ます。ファイルバーに「sample_mask.json」と「サンプル表示中」が出ていれば成功です。</dd>
            <dt>終わったら</dt>
            <dd>結果が表示されたら、次は表を読みます（ステップ 2）。このページに戻るときは、解析画面の見出し下にある「はじめての方へ：使い方を見る」を押します。</dd>
          </dl>
          <p className="small muted">選ぶとその場で解析が始まります（「解析を開始」のようなボタンはありません）。大きな枠にもファイルバーにも、ファイルをドラッグ＆ドロップできます。前の結果がある間は「解析中…（前回の結果を表示中）」と出て、完了すると新しい結果に差し替わります。</p>
          <details className="guide-details">
            <summary>読み込める JSON の形式</summary>
            <p className="small muted">読み込めるのは、課題で配布された 部屋・壁・ドアマスク.json（同梱サンプルはこれと同じデータ）と同じ形式（contours / image_data / image_width / image_height を含む JSON）だけです。PNG・JPEG・PDF は読み込めません。形式は大きな枠の「入力形式について」でも確認できます。</p>
          </details>
        </li>
        <li className="panel" id="step-2">
          <h2><span className="guide-num">2</span>表で壁面積を読む</h2>
          <dl className="guide-pair">
            <dt>やること</dt>
            <dd>図面の下（広い画面では右）にある結果表の、右端の「壁面積」列を見ます。手元に残すときは、結果表の上にある「CSV ダウンロード」を押すと room_wall_areas.csv が保存されます。</dd>
            <dt>画面に出るもの</dt>
            <dd>部屋ごとに「床面積・周長・壁長・壁なし長・控除ドア幅・壁面積」が 1 行ずつ並び、最後に合計行があります。壁面積は部屋の内側から見た壁の面積で、壁のない区間（壁なし長）は含めず、ドアの分（控除ドア幅）を引いた値です。画面上部のカードには「部屋数」「床面積 合計（部屋別の合算）」「壁面積 合計（内壁・両面計上）」が出ます。</dd>
            <dt>終わったら</dt>
            <dd>気になる部屋があれば、表のその行をクリックしてステップ 3 へ進みます。数値を保存するだけなら、表の上の「CSV ダウンロード」を押して終わりです。</dd>
          </dl>
          <p className="small muted">列の見出し（例：「壁面積」）を押すと並べ替えできます。一部の列は見出しにマウスを置くと説明が出ます。表の下の「壁面積の定義（詳細）」でも確認できます。画面幅が狭いときは「全項目を表示」にチェックを入れると、隠れている列が出ます。</p>
        </li>
        <li className="panel" id="step-3">
          <h2><span className="guide-num">3</span>部屋をクリックして根拠を見る</h2>
          <dl className="guide-pair">
            <dt>やること</dt>
            <dd>結果表の行か、図面の色が付いた部屋をクリックします。キーボードでは行に移動して Enter を押します。</dd>
            <dt>画面に出るもの</dt>
            <dd>図面でその部屋が青い枠で強調され、ほかの部屋は薄くなります。部屋の各辺に番号のバッジと色線が出て、図面のすぐ下に部屋名・床面積・壁面積を示す選択バーが出ます。続けて下の操作へ。</dd>
          </dl>
          <div className="legend" role="group" aria-label="図面の色の意味">
            <span><i aria-hidden="true" style={{ background: WALL_INTERVAL_COLOR }} />壁あり区間（濃い赤の実線）</span>
            <span><i aria-hidden="true" className="dashed" style={{ borderColor: OPENING_COLOR }} />壁なし区間（オレンジの破線）</span>
            <span><i aria-hidden="true" style={{ background: DOOR_COLOR }} />ドア（緑）</span>
            <span><i className="badge-legend" aria-hidden="true">1</i>辺番号（クリックで選択・内訳表と対応）</span>
            <span><i aria-hidden="true" style={{ background: SELECT_COLOR }} />選択中の部屋・辺（青）</span>
          </div>
          <dl className="guide-pair">
            <dt>次にやること</dt>
            <dd>選択バーの「算出根拠を見る ↓」を押します。表の選択中の行にも同じボタンがあります。</dd>
            <dt>次に出るもの</dt>
            <dd>画面下部の算出根拠パネルへ移動します（パネルは部屋を選んだ時点で出ています）。「壁面積（ドア控除後）」の値と「壁部分 − ドア控除 ＝ 壁面積」の式、「辺ごとの内訳」の表（辺長・壁長・壁なし・ドア・壁面積・計算式・区間の内訳）があり、表の合計はその部屋の壁面積と一致します。</dd>
            <dt>終わったら</dt>
            <dd>選択バーか、算出根拠パネルの見出し右にある「選択解除」を押すか、図面の何もない背景をクリックするか、Esc キーを押すと選択が外れます。同じ部屋をもう一度クリックしても外れます。</dd>
          </dl>
          <p className="small muted">内訳の行や図面の辺番号を押すと、その辺だけが青で強調されます。</p>
          <p className="small muted">「壁 ○ m」「ドア ○ m」のチップにマウスを置くかクリックすると、元になった壁・ドアの線分が図面で強調されます。</p>
          <p className="small muted">JSON の座標や線分 id と突き合わせるには、パネル最下部の「元データとの照合（座標・線分 id・JSON 記載値）」を開きます。</p>
          <p className="small muted">図面は「元画像」「部屋」「壁」「ドア」「部屋名」のチェックで表示を切り替え、「＋」「−」で拡大縮小、「全体」で元に戻せます。拡大しても計算結果は変わりません。</p>
          <p className="small muted">部屋が小さくて見づらいときは、図面ツールバーの「選択部屋に合わせる」で拡大できます。部屋を選んでいない状態で押すと「拡大する部屋を図面または表でクリックしてください。全体ボタンで取り消せます。」と出て、次に選んだ部屋に合わせて拡大します。</p>
          <p className="small muted">名前のない部屋（表に「名称未設定」）は、パネル見出し横の「名前を付ける」で画面上の表示名を付けられます。JSON は変更されず、別のファイルを読むと消えます。</p>
        </li>
      </ol>
      <section className="panel" aria-labelledby="guide-rules">
        <h2 id="guide-rules">計算のルール（固定・入力なし）</h2>
        <div className="guide-chips">
          <span className="cond-chip">天井高 2.4 m</span>
          <span className="cond-chip">ドア高 2.0 m</span>
          <span className="cond-chip">スケール 96.7 px ＝ 1.365 m</span>
        </div>
        <p>壁面積 ＝ 壁長 × 天井高 2.4 m − 控除ドア幅 × ドア高 2.0 m。壁が検出されなかった区間（表の「壁なし長」）は壁面積に含めません。ドアの上の壁は残し、窓は控除しません。</p>
        <p>壁面積は部屋の内側から見た面積です。2 つの部屋に挟まれた壁は両方の部屋に数えるため、「壁面積 合計（内壁・両面計上）」もその合算です。床面積は部屋の輪郭の頂点座標から計算した値で、部屋が重なっている場合は図面に紫の斜線が出て、カードに「重複を除いた床面積」も並びます。</p>
        <p className="small muted">天井高・ドア高・縮尺を変える入力欄はありません。解析画面の「課題指定の計算条件（固定）」は、いま適用されている値を確認するための表示です。縮尺の違う図面では実寸と一致しません。</p>
      </section>
      <section className="panel" aria-labelledby="guide-checks">
        <h2 id="guide-checks">「要確認」が表示されたら</h2>
        <dl className="guide-pair">
          <dt>画面に出るもの</dt>
          <dd>結果表の壁面積のセルと、上部の「壁面積 合計（内壁・両面計上）」カードに「要確認」の印が付き、図面の下の「解析結果の確認事項」に「壁面積は要確認です」と出ます。部屋を選ぶと、算出根拠パネルにも「壁面積は要確認: …」の説明が出ます。</dd>
          <dt>意味</dt>
          <dd>その部屋の輪郭に壁がほとんど対応付いていません。JSON に有効な壁の線がない、部屋の輪郭に沿う壁が見つからない、対応率（周長のうち壁として検出できた長さの割合）が 20% 未満、のいずれかです。壁面積が 0 m² でも「壁がない」とは限りません。ドアだけで区切られた開放的な空間でも出ることがあります。「要確認」が出ていない部屋も、図面と照らして確認する対象に含めてください。</dd>
          <dt>やること</dt>
          <dd>「壁面積は要確認です」の下にある「対象を確認」（対象の部屋がある項目に出ます）を押すと、その部屋が選ばれて図面へ移動します。図面の壁の線と部屋の輪郭を見比べ、元の JSON を確認してください。「診断メッセージ一覧」を開くと警告を種類ごとに見られます。CSV の「壁面積の注意事項」列にも同じ内容が残ります。</dd>
        </dl>
      </section>
      <section className="panel" aria-labelledby="guide-trouble">
        <h2 id="guide-trouble">困ったとき</h2>
        <dl className="guide-faq">
          <dt>「エラー: バックエンド API に接続できません。uvicorn が起動しているか確認してください。」と出る</dt>
          <dd>バックエンド（計算サーバー）が起動していない可能性があります。リポジトリ直下の README.md の「起動・操作」に従って起動してください（start.sh で両方をまとめて起動できます）。起動したら、もう一度読み込んでください。最初の読み込みで出た場合は大きな枠の「サンプルで試す」か「JSON ファイルを選択」、結果が表示されている場合はファイルバーの「別の JSON を選択」を使います。前の結果は消えません。</dd>
          <dt>図面も表も出ない</dt>
          <dd>「JSON を選んで始める」から開いた画面は、ファイルを選ぶまで図面と表が出ません。枠の「サンプルで試す」を押すと同梱の図面で結果が出ます。</dd>
          <dt>部屋に「名称未設定」と付いている</dt>
          <dd>JSON に部屋名（room_name）がありません。ステップ 3 の「名前を付ける」で画面上の表示名を付けられます。名前を付けた部屋は「診断メッセージ一覧」の「部屋名が未設定」から外れます。</dd>
        </dl>
      </section>
      <details className="definition guide-terms">
        <summary>ここで使う言葉</summary>
        <dl className="guide-terms-list">
          <dt>床面積</dt><dd>部屋の輪郭の頂点座標から計算した面積 [m²]。内側に穴があれば除きます。</dd>
          <dt>周長</dt><dd>部屋の輪郭を一周した長さ [m]。穴があれば内側の周も含みます。</dd>
          <dt>壁長</dt><dd>周長のうち、壁の線が輪郭に沿って検出された長さ [m]。</dd>
          <dt>壁なし長</dt><dd>周長のうち、壁の線が見つからなかった長さ [m]。壁面積には含めません。図面ではオレンジの破線、CSV では「開口長[m]」です。</dd>
          <dt>控除ドア幅</dt><dd>壁の上にあるドアの幅の合計 [m] と箇所数。この幅 × ドア高 2.0 m を壁面積から引きます。壁のない所にあるドアは引きません。CSV では「ドア長[m]」「ドア数」です。</dd>
          <dt>壁面積（ドア控除後）</dt><dd>壁長 × 天井高 2.4 m − 控除ドア幅 × ドア高 2.0 m。算出根拠パネルでは「壁部分」（壁長 × 天井高）から「ドア控除」（控除ドア幅 × ドア高）を引く形で示します。</dd>
          <dt>対応率</dt><dd>部屋の周長のうち、壁として検出できた長さの割合。0% なら「壁が未検出の部屋」、20% 未満なら「壁の対応率が低い部屋」として「要確認」になります。</dd>
          <dt>辺番号</dt><dd>部屋を選ぶと図面の各辺の中央に出る 1 始まりの番号。「辺ごとの内訳」と「元データとの照合」の行に対応します。</dd>
          <dt>線分 id</dt><dd>JSON に入っている壁・ドアの線ひとつひとつの番号。「区間の内訳」のチップで、どの線が計算に使われたかを図面で確かめられます。</dd>
          <dt>サンプル表示中</dt><dd>同梱の sample_mask.json を表示していることを示す目印。このとき「サンプルを読み込む」ボタンは出ません。</dd>
        </dl>
      </details>
      <p>読み終わったら、ここから始められます。上の「まず 1 分で結果を見る」と同じ画面が開きます。</p>
      <nav className="guide-actions" aria-label="解析を始める">
        <Link className="btn btn-primary btn-lg" href="/?sample=1">サンプルで試す</Link>
        <Link className="btn btn-lg" href="/?start=upload">JSON を選んで始める</Link>
      </nav>
    </main>
  );
}
