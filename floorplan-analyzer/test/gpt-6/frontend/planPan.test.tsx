// @vitest-environment jsdom
import { useRef } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/react";
import { usePlanPan } from "../../../frontend/src/hooks/usePlanPan";
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function Harness({ select }: { select: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const pan = usePlanPan(ref);
  return <div ref={ref} style={{ overflow: "auto" }}><svg {...pan}><rect onClick={select} /></svg></div>;
}
function setup() {
  vi.stubGlobal("PointerEvent", class extends MouseEvent {
    pointerId: number; pointerType: string;
    constructor(type: string, init: PointerEventInit = {}) { super(type, init); this.pointerId = init.pointerId ?? 1; this.pointerType = init.pointerType ?? "mouse"; }
  });
  const select = vi.fn();
  const { container } = render(<Harness select={select} />);
  const svg = container.querySelector("svg")!, rect = container.querySelector("rect")!, canvas = svg.parentElement!;
  let captured = false;
  svg.setPointerCapture = vi.fn(() => { captured = true; });
  svg.hasPointerCapture = vi.fn(() => captured);
  svg.releasePointerCapture = vi.fn(() => { captured = false; });
  Object.defineProperties(canvas, { clientWidth: { value: 300 }, clientHeight: { value: 200 }, scrollWidth: { value: 900 }, scrollHeight: { value: 800 } });
  canvas.scrollLeft = 100; canvas.scrollTop = 150;
  return { svg, rect, canvas, select };
}

test("mouse drag pans both axes, suppresses selection, and releases capture", () => {
  const { svg, rect, canvas, select } = setup();
  fireEvent.pointerDown(rect, { clientX: 100, clientY: 100, button: 0 });
  fireEvent.pointerMove(svg, { clientX: 70, clientY: 60 });
  expect(canvas.scrollLeft).toBe(130); expect(canvas.scrollTop).toBe(190);
  expect(canvas.dataset.panning).toBe("true");
  fireEvent.pointerUp(svg);
  fireEvent.click(rect, { detail: 1 });
  expect(select).not.toHaveBeenCalled();
  expect(canvas.dataset.panning).toBeUndefined();
  expect(svg.releasePointerCapture).toHaveBeenCalled();
  fireEvent.pointerDown(rect, { clientX: 50, clientY: 50, button: 0 });
  fireEvent.pointerMove(svg, { clientX: 52, clientY: 51 });
  fireEvent.pointerUp(rect); fireEvent.click(rect, { detail: 1 });
  expect(select).toHaveBeenCalledOnce();
});

test("scrollbar, touch, and right button retain native behavior; cancel ends dragging", () => {
  const { svg, rect, canvas } = setup();
  fireEvent.pointerDown(canvas, { button: 0 }); // scrollbar is outside SVG
  fireEvent.pointerMove(svg, { clientX: -30, clientY: -40 });
  expect(canvas.scrollTop).toBe(150);
  for (const init of [{ pointerType: "touch", button: 0 }, { pointerType: "mouse", button: 2 }]) {
    fireEvent.pointerDown(rect, { ...init, clientX: 100, clientY: 100 });
    fireEvent.pointerMove(svg, { ...init, clientX: 40, clientY: 40 });
    expect(canvas.scrollTop).toBe(150);
  }
  fireEvent.pointerDown(rect, { button: 0, clientX: 100, clientY: 100 });
  fireEvent.pointerMove(svg, { clientX: 80, clientY: 80 });
  fireEvent.pointerCancel(svg);
  expect(canvas.dataset.panning).toBeUndefined();
  fireEvent.pointerMove(svg, { clientX: 40, clientY: 40 });
  expect(canvas.scrollTop).toBe(170);
  expect(canvas.style.overflow).toBe("auto");
});


test("drag clamps at scroll limits without oscillating or selecting", () => {
  const { svg, rect, canvas, select } = setup();
  fireEvent.pointerDown(rect, { clientX: 100, clientY: 100, button: 0 });
  for (const y of [-1000, -1005, -1000]) {
    fireEvent.pointerMove(svg, { clientX: -1000, clientY: y });
    expect(canvas.scrollTop).toBe(600);
    expect(canvas.scrollLeft).toBe(600);
  }
  fireEvent.pointerMove(svg, { clientX: 1000, clientY: 1000 });
  expect(canvas.scrollTop).toBe(0); expect(canvas.scrollLeft).toBe(0);
  fireEvent.pointerUp(svg); fireEvent.click(rect, { detail: 1 });
  expect(select).not.toHaveBeenCalled();
});
