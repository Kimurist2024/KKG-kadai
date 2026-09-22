import { useRef } from "react";
import type { MouseEvent, PointerEvent, RefObject } from "react";

/** SVG上のマウスドラッグだけを扱い、ネイティブのスクロールバー・タッチ操作を残す。 */
export function usePlanPan(canvasRef: RefObject<HTMLDivElement | null>) {
  const drag = useRef<{ id: number; x: number; y: number; left: number; top: number; moved: boolean } | null>(null);
  const suppressClick = useRef(false);

  const onPointerDown = (event: PointerEvent<SVGSVGElement>) => {
    suppressClick.current = false;
    const canvas = canvasRef.current;
    if (!canvas || event.pointerType !== "mouse" || event.button !== 0) return;
    if (canvas.scrollWidth <= canvas.clientWidth && canvas.scrollHeight <= canvas.clientHeight) return;
    // 標準の文字選択・フォーカスによる自動スクロールと競合させない。
    event.preventDefault();
    drag.current = { id: event.pointerId, x: event.clientX, y: event.clientY, left: canvas.scrollLeft, top: canvas.scrollTop, moved: false };
  };
  const onPointerMove = (event: PointerEvent<SVGSVGElement>) => {
    const start = drag.current, canvas = canvasRef.current;
    if (!start || !canvas || start.id !== event.pointerId) return;
    const dx = event.clientX - start.x, dy = event.clientY - start.y;
    if (!start.moved && Math.hypot(dx, dy) < 5) return;
    if (!start.moved) {
      start.moved = true;
      suppressClick.current = true;
      event.currentTarget.setPointerCapture(event.pointerId);
      canvas.dataset.panning = "true";
    }
    event.preventDefault();
    canvas.scrollLeft = Math.max(0, Math.min(canvas.scrollWidth - canvas.clientWidth, start.left - dx));
    canvas.scrollTop = Math.max(0, Math.min(canvas.scrollHeight - canvas.clientHeight, start.top - dy));
  };
  const finish = (event: PointerEvent<SVGSVGElement>) => {
    if (drag.current?.id !== event.pointerId) return;
    drag.current = null;
    if (canvasRef.current) delete canvasRef.current.dataset.panning;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  };
  const onClickCapture = (event: MouseEvent) => {
    if (suppressClick.current && event.detail !== 0) {
      event.preventDefault();
      event.stopPropagation();
    }
    suppressClick.current = false;
  };
  return { onPointerDown, onPointerMove, onPointerUp: finish, onPointerCancel: finish, onLostPointerCapture: finish,
    onPointerLeave: (event: PointerEvent<SVGSVGElement>) => { if (!drag.current?.moved) finish(event); }, onClickCapture };
}
