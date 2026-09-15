// @vitest-environment jsdom
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import SettingsPanel from "../../../frontend/src/components/SettingsPanel";
import App from "../../../frontend/src/App";
import { roomsToCsv } from "../../../frontend/src/format";
import { wallWarningsForRoom } from "../../../frontend/src/warnings";
import { useAnalysis } from "../../../frontend/src/hooks/useAnalysis";
import { analyzeFile } from "../../../frontend/src/api";
import { DEFAULT_SETTINGS, type AnalyzeResponse } from "../../../frontend/src/types";
vi.mock("../../../frontend/src/api", () => ({ analyzeFile: vi.fn() }));
const response = (s = DEFAULT_SETTINGS) => ({ settings: s } as AnalyzeResponse);
const file = (name: string, text = async () => "{}") => Object.assign(new File(["{}"], name), { text });
const wallResult: AnalyzeResponse = {
  image: { width: 100, height: 100, mime_type: null, has_image: false }, timestamp: null,
  settings: { ...DEFAULT_SETTINGS, meters_per_px: 0.01 },
  summary: { room_count: 1, wall_count: 0, door_count: 0, total_floor_area_m2: 1, total_wall_area_m2: 0 },
  rooms: [{ id: 1, name: "Room", room_name: "Room", color: "#abc", vertices: [{x:0,y:0},{x:100,y:0},{x:100,y:100},{x:0,y:100}],
    floor_area_px2: 10000, floor_area_m2: 1, perimeter_px: 400, perimeter_m: 4,
    source_area_px2: null, source_perimeter_px: null, wall_length_m: 0, opening_length_m: 4,
    door_length_m: 0, door_count: 0, wall_area_gross_m2: 0, door_area_m2: 0, wall_area_m2: 0, edges: [] }],
  walls: [], doors: [], warnings: [{ code: "missing_wall_data", contour_id: null, message: "壁データがありません。" }],
};
beforeEach(() => { vi.mocked(analyzeFile).mockReset(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("wall warning scope and CSV preserve missing-wall caveat", () => {
  expect(wallWarningsForRoom(wallResult, 1)).toHaveLength(1);
  expect(wallWarningsForRoom({ ...wallResult, warnings: [{ code: "no_room_walls", contour_id: 2, message: "未検出" }] }, 1)).toHaveLength(0);
  const csv = roomsToCsv(wallResult);
  expect(csv).toContain("壁面積の注意事項");
  expect(csv).toContain("壁データがありません。");
  expect(csv).toContain("要確認の壁面積を含みます");
  const aiCsv = roomsToCsv({ ...wallResult, warnings: [{ code: "ai_generated", contour_id: null, message: "AI による参考値" }] });
  expect(aiCsv).toContain("解析の注意事項");
  expect(aiCsv.split("AI による参考値")).toHaveLength(3); // 部屋行・合計行とも注意を残す。
});

test("app gates upload, shows wall warning, hides old result during next scale review", async () => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.mocked(analyzeFile).mockResolvedValue(wallResult);
  const { container } = render(<App />);
  const upload = () => fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [file("drawing.json")] } });
  upload();
  await screen.findByRole("heading", { name: "この図面の縮尺を確認" });
  expect(analyzeFile).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("画像上の長さ"), { target: { value: "100" } });
  fireEvent.change(screen.getByLabelText("実寸"), { target: { value: "1" } });
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "縮尺を確認して解析" }));
  await screen.findByText("壁面積は要確認です");
  expect(screen.getAllByText("要確認").length).toBeGreaterThanOrEqual(2);
  expect(screen.getByRole("button", { name: /CSV/ })).toBeTruthy();
  upload();
  await screen.findByRole("heading", { name: "この図面の縮尺を確認" });
  expect(screen.queryByRole("button", { name: /CSV/ })).toBeNull();
  expect(screen.queryByText("壁面積は要確認です")).toBeNull();
  expect(analyzeFile).toHaveBeenCalledTimes(1);
});

test("new drawing requires explicit scale and acknowledgement; changing scale clears acknowledgement", () => {
  const apply = vi.fn();
  render(<SettingsPanel applied={DEFAULT_SETTINGS} disabled={false} onApply={apply} confirmScale />);
  const px = screen.getByLabelText("画像上の長さ");
  const meters = screen.getByLabelText("実寸");
  const button = screen.getByRole("button", { name: "縮尺を確認して解析" }) as HTMLButtonElement;
  expect((px as HTMLInputElement).value).toBe("");
  expect(button.disabled).toBe(true);
  fireEvent.change(px, { target: { value: "949" } });
  fireEvent.change(meters, { target: { value: "44.65" } });
  expect(button.disabled).toBe(true);
  fireEvent.click(screen.getByRole("checkbox"));
  expect(button.disabled).toBe(false);
  fireEvent.change(meters, { target: { value: "44.66" } });
  expect(button.disabled).toBe(true);
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(button);
  expect(apply).toHaveBeenCalledWith(expect.objectContaining({ scale_px: 949, scale_m: 44.66 }));
});

test("upload waits for scale; another file waits again and cancellation restores prior snapshot", async () => {
  const { result } = renderHook(useAnalysis);
  const a=file("a.json"), b=file("b.json");
  await act(() => result.current.loadFile(a));
  expect(analyzeFile).not.toHaveBeenCalled();
  const s={...DEFAULT_SETTINGS,scale_px:949,scale_m:44.65};
  vi.mocked(analyzeFile).mockResolvedValue(response(s));
  act(() => result.current.reanalyze(s));
  await waitFor(() => expect(result.current.pending).toBeNull());
  expect(result.current.file).toBe(a);
  await act(() => result.current.loadFile(b));
  expect(analyzeFile).toHaveBeenCalledTimes(1);
  expect(result.current.pending?.file).toBe(b);
  act(() => result.current.cancelPending());
  expect(result.current.file).toBe(a);
  expect(result.current.appliedSettings).toEqual(s);
});

test("late image read and late analysis cannot overwrite a newer drawing", async () => {
  const { result }=renderHook(useAnalysis);
  let finish!: (s:string)=>void;
  let loading!: Promise<void>;
  act(() => { loading=result.current.loadFile(file("slow.json",()=>new Promise(r=>{finish=r;}))); });
  await act(() => result.current.loadFile(file("current.json")));
  await act(async () => { finish("{}"); await loading; });
  expect(result.current.pending?.file.name).toBe("current.json");
  let resolve!: (r:AnalyzeResponse)=>void;
  vi.mocked(analyzeFile).mockImplementation(()=>new Promise(r=>{resolve=r;}));
  act(()=>result.current.reanalyze(DEFAULT_SETTINGS));
  await act(()=>result.current.loadFile(file("newest.json")));
  await act(async()=>{resolve(response());});
  expect(result.current.pending?.file.name).toBe("newest.json");
  expect(result.current.result).toBeNull();
});

test("failed analysis remains pending for retry; sample always uses its known scale", async () => {
  const { result }=renderHook(useAnalysis);
  await act(()=>result.current.loadFile(file("a.json")));
  vi.mocked(analyzeFile).mockRejectedValueOnce(new Error("network"));
  act(()=>result.current.reanalyze({...DEFAULT_SETTINGS,scale_m:100}));
  await waitFor(()=>expect(result.current.status.state).toBe("error"));
  expect(result.current.pending?.file.name).toBe("a.json");
  vi.stubGlobal("fetch",vi.fn().mockResolvedValue({ok:true,blob:async()=>new Blob(["{}"])}));
  vi.mocked(analyzeFile).mockResolvedValue(response());
  await act(()=>result.current.loadSample());
  expect(vi.mocked(analyzeFile).mock.lastCall?.[1]).toEqual(DEFAULT_SETTINGS);
  expect(result.current.pending).toBeNull();
});


test("initial screen loads the sample into the compact workspace without a click", async () => {
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  const fetchSample = vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(["{}"]) });
  vi.stubGlobal("fetch", fetchSample);
  vi.mocked(analyzeFile).mockResolvedValue(wallResult);
  const { container } = render(<App />);
  await screen.findByText("サンプル表示中");
  expect(fetchSample).toHaveBeenCalledWith("/sample_mask.json", expect.anything());
  expect(container.querySelector(".dropzone.compact")).not.toBeNull();
  expect(container.querySelector(".dropzone-body")).toBeNull();
  expect(screen.getByRole("img", { name: "平面図の解析結果" })).toBeTruthy();
  expect(container.querySelector("table.rooms")).not.toBeNull();
  expect(screen.queryByRole("button", { name: "サンプルで試す" })).toBeNull();
});
