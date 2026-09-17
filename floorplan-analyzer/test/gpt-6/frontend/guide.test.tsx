// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import GuidePage from "../../../frontend/src/app/guide/page";

afterEach(cleanup);
test("guide explains the three steps and links to sample and upload entry points", () => {
  render(<GuidePage />);
  expect(screen.getAllByRole("listitem")).toHaveLength(3);
  expect(screen.getByRole("heading", { name: "「要確認」が表示されたら" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "サンプルで試す" }).getAttribute("href")).toBe("/?sample=1");
  expect(screen.getByRole("link", { name: "JSON を選んで始める" }).getAttribute("href")).toBe("/?start=upload");
});

import { DOOR_COLOR, OPENING_COLOR, SELECT_COLOR, WALL_INTERVAL_COLOR } from "../../../frontend/src/components/plan/colors";

test("guide provides distinct navigation and the required heading hierarchy", () => {
  const { container } = render(<GuidePage />);
  const hero = container.querySelector(".guide-hero");
  expect(hero?.tagName).toBe("SECTION");
  expect(hero?.getAttribute("aria-labelledby")).toBe("guide-hero-heading");
  const heroHeading = hero?.querySelector("#guide-hero-heading");
  expect(heroHeading?.tagName).toBe("H2");
  expect(heroHeading?.textContent).toBe("まず 1 分で結果を見る");
  const heroNav = screen.getByRole("navigation", { name: "いますぐ試す" });
  expect(hero?.contains(heroNav)).toBe(true);
  expect(heroNav.querySelectorAll("a")).toHaveLength(2);
  for (const [name, href] of [
    ["サンプルで試す：同梱の図面をすぐ開く", "/?sample=1"],
    ["JSON を選んで始める：自分のファイルを選ぶ", "/?start=upload"],
    ["解析画面へ", "/"],
  ]) {
    expect(screen.getByRole("link", { name }).getAttribute("href")).toBe(href);
  }
  const allowedHrefs = new Set(["/", "/?sample=1", "/?start=upload"]);
  for (const link of screen.getAllByRole("link")) {
    expect(allowedHrefs.has(link.getAttribute("href") ?? "")).toBe(true);
  }
  expect(screen.getAllByRole("navigation")).toHaveLength(3);
  for (const name of ["解析画面への移動", "いますぐ試す", "解析を始める"]) {
    expect(screen.getByRole("navigation", { name })).toBeTruthy();
  }
  for (const name of [/開くだけで結果が出ます/, /表で壁面積を読む/, /部屋をクリックして根拠を見る/]) {
    expect(screen.getByRole("heading", { level: 2, name })).toBeTruthy();
  }
  for (const name of ["まず 1 分で結果を見る", "解析画面の並び", "計算のルール（固定・入力なし）", "困ったとき"]) {
    expect(screen.getByRole("heading", { level: 2, name })).toBeTruthy();
  }
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  expect(screen.getAllByRole("heading", { name: "「要確認」が表示されたら" })).toHaveLength(1);
  expect(screen.queryAllByRole("heading", { level: 3 })).toHaveLength(0);
});

test("guide uses the current screen labels and fixed calculation conditions", () => {
  const { container } = render(<GuidePage />);
  const text = container.textContent ?? "";
  for (const label of [
    "別の JSON を選択", "JSON ファイルを選択", "サンプル表示中", "算出根拠を見る ↓",
    "選択解除", "選択部屋に合わせる", "CSV ダウンロード", "全項目を表示", "対象を確認",
    "解析結果の確認事項", "診断メッセージ一覧", "名前を付ける",
    "ドラッグ＆ドロップ", "解析中…（前回の結果を表示中）",
    "元データとの照合（座標・線分 id・JSON 記載値）", "壁面積の定義（詳細）",
    "壁面積 ＝ 壁長 × 天井高 2.4 m − 控除ドア幅 × ドア高 2.0 m",
    "エラー: バックエンド API に接続できません。uvicorn が起動しているか確認してください。",
  ]) {
    expect(text).toContain(label);
  }
  expect(Array.from(container.querySelectorAll(".cond-chip"), (chip) => chip.textContent)).toEqual([
    "天井高 2.4 m", "ドア高 2.0 m", "スケール 96.7 px ＝ 1.365 m",
  ]);
  for (const label of [
    "画像から AI", "AI 利用トークン", "計算条件を変更", "この図面の縮尺を確認",
    "ホイールで拡大", "赤字", "赤い",
  ]) {
    expect(text).not.toContain(label);
  }
});

test("guide preserves screen order, native disclosures, three steps, and an accessible legend", () => {
  const { container } = render(<GuidePage />);
  const text = container.textContent ?? "";
  let previousIndex = -1;
  for (const label of [
    "見出しと集計カード", "ファイルバー", "課題指定の計算条件（固定）", "図面（", "結果表（", "算出根拠パネル（",
  ]) {
    const index = text.indexOf(label);
    expect(index).toBeGreaterThan(previousIndex);
    previousIndex = index;
  }
  expect(container.querySelectorAll(".guide-flow-row")).toHaveLength(6);
  expect(Array.from(container.querySelectorAll(".guide-flow-row .guide-num"), (badge) => badge.textContent))
    .toEqual(["2", "1", "1", "3", "2", "3"]);
  const flowBadges = container.querySelectorAll(".guide-flow-row .guide-num");
  expect(flowBadges).toHaveLength(6);
  for (const badge of flowBadges) {
    expect(badge.getAttribute("role")).toBe("img");
    expect(badge.getAttribute("aria-label")).toBe(`ステップ ${badge.textContent}`);
  }
  const stepBadges = container.querySelectorAll(".guide-steps h2 .guide-num");
  expect(stepBadges).toHaveLength(3);
  for (const badge of stepBadges) {
    expect(badge.getAttribute("role")).toBeNull();
  }
  expect(Array.from(container.querySelectorAll("details summary"), (summary) => summary.textContent))
    .toEqual(["読み込める JSON の形式", "ここで使う言葉"]);
  expect(container.querySelectorAll(".guide-details > p")).toHaveLength(1);
  expect(container.querySelectorAll(".guide-terms-list > dt")).toHaveLength(10);
  expect(container.querySelectorAll(".guide-terms-list > dd")).toHaveLength(10);
  expect(container.querySelectorAll("ul, ol li li")).toHaveLength(0);
  expect(container.querySelectorAll("ol.guide-steps > li")).toHaveLength(3);
  expect(Array.from(container.querySelectorAll("ol.guide-steps > li"), (step) => step.id))
    .toEqual(["step-1", "step-2", "step-3"]);
  const legend = container.querySelector(".legend");
  expect(legend).not.toBeNull();
  expect(legend?.getAttribute("aria-label")).toBe("図面の色の意味");
  expect(legend?.querySelectorAll("span")).toHaveLength(5);
  const swatches = legend?.querySelectorAll("i");
  expect(swatches).toHaveLength(5);
  swatches?.forEach((swatch) => expect(swatch.getAttribute("aria-hidden")).toBe("true"));
  for (const [label, property, color] of [
    ["壁あり区間", "background", WALL_INTERVAL_COLOR],
    ["壁なし区間", "borderColor", OPENING_COLOR],
    ["ドア", "background", DOOR_COLOR],
    ["選択中", "background", SELECT_COLOR],
  ] as const) {
    const swatch = Array.from(legend?.querySelectorAll("span") ?? [])
      .find((item) => item.textContent?.startsWith(label))?.querySelector("i");
    expect(swatch).toBeTruthy();
    const probe = document.createElement("div");
    probe.style[property] = color;
    expect((swatch as HTMLElement).style[property]).toBe(probe.style[property]);
  }
  for (const label of ["壁あり区間", "壁なし区間", "辺番号"]) {
    expect(legend?.textContent).toContain(label);
  }
});

test("guide retains its page metadata", async () => {
  const { metadata } = await import("../../../frontend/src/app/guide/page");
  expect(metadata.title).toBe("使い方 | 平面図 面積・壁面積 解析");
});
