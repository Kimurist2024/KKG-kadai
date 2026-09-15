// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import AiImportPanel from "../../../frontend/src/components/AiImportPanel";
import { recognizeImage } from "../../../frontend/src/api";
import type { RecognitionResponse } from "../../../frontend/src/types";

vi.mock("../../../frontend/src/api", () => ({ recognizeImage: vi.fn() }));
afterEach(() => { cleanup(); vi.mocked(recognizeImage).mockReset(); });
const response: RecognitionResponse = {
  model: "test-model", warnings: ["部屋の位置を確認してください"],
  mask: { image_width: 100, image_height: 100, image_data: { base64: "abc", mime_type: "image/png" },
    contours: [{ id: 1, label_id: 1, color: "blue", isLine: false, room_name: "Room", vertices: [{x:0,y:0},{x:100,y:0},{x:0,y:100}] }],
    ai_recognition: { model: "test-model", warnings: ["要確認"] } },
};

function setup(onFile = vi.fn()) {
  render(<AiImportPanel onFile={onFile} disabled={false} />);
  fireEvent.click(screen.getByRole("button", { name: "画像から AI で輪郭を作成" }));
  fireEvent.change(screen.getByLabelText("図面画像（10 MB 以下）"), { target: { files: [new File(["png"], "drawing.png", {type:"image/png"})] } });
  fireEvent.change(screen.getByLabelText("AI 利用トークン"), { target: { value: "site-token" } });
  return onFile;
}

test("sending requires consent; draft cannot enter analysis until reviewed", async () => {
  vi.mocked(recognizeImage).mockResolvedValue(response);
  const onFile = setup();
  const start = screen.getByRole("button", { name: "AI で輪郭を認識" }) as HTMLButtonElement;
  expect(start.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText("この画像を OpenAI に送信して認識する"));
  fireEvent.click(start);
  await screen.findByRole("img", { name: "元画像に重ねた AI の認識候補" });
  expect(recognizeImage).toHaveBeenCalledWith(expect.any(File), "site-token", expect.any(AbortSignal));
  const proceed = screen.getByRole("button", { name: "この認識結果で縮尺確認へ" }) as HTMLButtonElement;
  expect(proceed.disabled).toBe(true);
  expect(onFile).not.toHaveBeenCalled();
  fireEvent.click(screen.getByLabelText("認識した部屋・壁・ドアの輪郭を図面と照合しました"));
  fireEvent.click(proceed);
  expect(onFile).toHaveBeenCalledOnce();
  expect(onFile.mock.calls[0][0].name).toBe("drawing.ai-mask.json");
});

test("cancelled recognition cannot expose a late response; replacing image resets consent", async () => {
  let finish!: (value: RecognitionResponse) => void;
  vi.mocked(recognizeImage).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  setup();
  fireEvent.click(screen.getByLabelText("この画像を OpenAI に送信して認識する"));
  fireEvent.click(screen.getByRole("button", { name: "AI で輪郭を認識" }));
  fireEvent.click(screen.getByRole("button", { name: "認識の待機を取り消す" }));
  await act(async () => { finish(response); });
  expect(screen.queryByRole("img")).toBeNull();
  fireEvent.change(screen.getByLabelText("図面画像（10 MB 以下）"), { target: { files: [new File(["x"], "b.jpg")] } });
  expect((screen.getByLabelText("この画像を OpenAI に送信して認識する") as HTMLInputElement).checked).toBe(false);
});

test("service failure is shown without handing a draft to analysis", async () => {
  vi.mocked(recognizeImage).mockRejectedValue(new Error("画像 AI は未設定です"));
  const onFile = setup();
  fireEvent.click(screen.getByLabelText("この画像を OpenAI に送信して認識する"));
  fireEvent.click(screen.getByRole("button", { name: "AI で輪郭を認識" }));
  expect((await screen.findByRole("alert")).textContent).toContain("未設定");
  expect(onFile).not.toHaveBeenCalled();
});
