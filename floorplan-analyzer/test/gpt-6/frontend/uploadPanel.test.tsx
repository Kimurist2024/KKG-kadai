// @vitest-environment jsdom
import { afterEach, expect, test } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import UploadPanel from "../../../frontend/src/components/UploadPanel";

afterEach(cleanup);
const noop = () => {};

test("while the sample is loading, the file bar explains the wait instead of asking for a file", () => {
  render(<UploadPanel fileName={null} loading compact onFile={noop} onLoadSample={noop} />);
  expect(screen.getByText("サンプル図面を読み込み中…")).toBeTruthy();
  expect(screen.getByText("完了すると図面と結果表が下に表示されます")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "サンプルを読み込む" })).toBeNull();
  expect(screen.queryByText("ファイル未選択")).toBeNull();
});

test("after loading, the sample badge differs from condition chips and drop is advertised", () => {
  const { container } = render(<UploadPanel fileName="sample_mask.json" loading={false} compact isSample onFile={noop} onLoadSample={noop} />);
  expect(screen.getByText("sample_mask.json")).toBeTruthy();
  expect(container.querySelector(".file-badge")?.textContent).toBe("サンプル表示中");
  expect(screen.getAllByText("サンプル表示中")).toHaveLength(1);
  expect(container.querySelector(".cond-chip")).toBeNull();
  expect(screen.getByText("JSON をこの行にドロップしても読み込めます")).toBeTruthy();
  expect(screen.getByRole("button", { name: "別の JSON を選択" })).toBeTruthy();
});

test("a user file restores the reload-sample button; the large dropzone is unchanged", () => {
  render(<UploadPanel fileName="drawing.json" loading={false} compact onFile={noop} onLoadSample={noop} />);
  expect(screen.getByText("drawing.json")).toBeTruthy();
  expect(screen.getByRole("button", { name: "サンプルを読み込む" })).toBeTruthy();
  expect(screen.queryByText("サンプル表示中")).toBeNull();
  cleanup();
  render(<UploadPanel fileName={null} loading={false} onFile={noop} onLoadSample={noop} />);
  expect(screen.getByRole("button", { name: "JSON ファイルを選択" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "サンプルで試す" })).toBeTruthy();
  expect(screen.getByText("入力形式について")).toBeTruthy();
});
