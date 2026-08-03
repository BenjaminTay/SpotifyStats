import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, useNavigate } from "react-router-dom";

import { ScrollToTop } from "@/App";

function NavigationControls() {
  const navigate = useNavigate();
  return (
    <>
      <button type="button" onClick={() => navigate("?metadata=track-credits")}>切换查询参数</button>
      <button type="button" onClick={() => navigate("/other")}>切换页面</button>
    </>
  );
}

describe("ScrollToTop", () => {
  beforeEach(() => {
    window.scrollTo = vi.fn();
  });

  it("preserves scroll for same-page query changes and resets for path changes", async () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <ScrollToTop />
        <NavigationControls />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "切换查询参数" }));
    await waitFor(() => expect(window.scrollTo).not.toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "切换页面" }));
    await waitFor(() => expect(window.scrollTo).toHaveBeenCalledWith(0, 0));
  });
});
