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
