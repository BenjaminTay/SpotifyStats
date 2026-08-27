import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { MusicMetadataSection } from "@/features/settings/components/MusicMetadataSection";

vi.mock("@/features/settings/components/TrackCreditManager", () => ({
  TrackCreditManager: ({ initialTrackId }: { initialTrackId?: number | null }) => (
    <div data-testid="track-credit-manager">track #{initialTrackId ?? "none"}</div>
  ),
}));
vi.mock("@/features/settings/components/VersionMergeSection", () => ({
  VersionMergeSection: ({
    initialObjectType,
    initialArtistFilter,
    initialCanonicalName,
    initialTrackId,
  }: {
    initialObjectType: string;
    initialArtistFilter?: string;
    initialCanonicalName?: string;
    initialTrackId?: number | null;
  }) => (
    <div data-testid="version-merge-workspace">
      {initialObjectType} ·
      {initialArtistFilter} · {initialCanonicalName} · {initialTrackId ?? "none"}
    </div>
  ),
}));
vi.mock("@/features/settings/components/GenreDataHealthSection", () => ({
  GenreDataHealthSection: ({ embedded }: { embedded?: boolean }) => (
    <div data-testid="genre-language-health">embedded:{String(embedded)}</div>
  ),
}));
vi.mock("@/features/settings/components/ArtistIdentitySection", () => ({
  ArtistIdentitySection: ({ initialSearch }: { initialSearch?: string }) => (
    <div data-testid="artist-identity">{initialSearch}</div>
  ),
}));

function renderRoute(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/settings" element={<MusicMetadataSection />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("MusicMetadataSection", () => {
  beforeEach(() => {
    HTMLElement.prototype.scrollIntoView = vi.fn();
    localStorage.clear();
  });

  it("matches the numbered settings header and renders four peer modules", async () => {
    renderRoute("/settings");
    expect(screen.getByText("05 · 音乐源数据管理")).toBeInTheDocument();
    expect(screen.queryByText(/直接编辑工具/)).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /归并与版本/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /曲目署名/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /艺人身份/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /流派与语言/ })).toBeInTheDocument();
    expect(screen.queryByText(/操作理由|证据来源|审批/)).not.toBeInTheDocument();
  });

  it("shows one shared merge-level control and one merge workspace", async () => {
    renderRoute("/settings?metadata=merge");
    expect(screen.getByRole("radiogroup", { name: "默认归并级别" })).not.toBeVisible();
    fireEvent.click(screen.getByText("统计展示默认值"));
    expect(screen.getByRole("radiogroup", { name: "默认归并级别" })).toBeVisible();
    expect(screen.getAllByRole("radiogroup", { name: "默认归并级别" })).toHaveLength(1);
    expect(screen.getAllByRole("radio")).toHaveLength(2);
    expect(screen.queryByRole("radio", { name: /L1/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "L3 同一作品" }));
    expect(localStorage.getItem("spotify_stats_merge_level")).toBe("3");
    expect(await screen.findByTestId("version-merge-workspace")).toHaveTextContent("track");
    expect(screen.queryByRole("tablist", { name: "归并内容类别" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("radiogroup", { name: "默认归并级别" })).toHaveLength(1);
  });

  it("keeps normal metadata tab switches at the current scroll position", async () => {
    renderRoute("/settings");
    fireEvent.click(screen.getByRole("tab", { name: /曲目署名/ }));
    expect(await screen.findByTestId("track-credit-manager")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: /艺人身份/ }));
    expect(await screen.findByTestId("artist-identity")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: /流派与语言/ }));
    expect(await screen.findByTestId("genre-language-health")).toHaveTextContent("embedded:true");
    expect(HTMLElement.prototype.scrollIntoView).not.toHaveBeenCalled();
  });

  it("deep-links to the exact track module, prefills it and focuses the panel", async () => {
    renderRoute(
      "/settings?metadata=track-credits&track_id=175&return_to=%2Fmusic%2Ftracks%2F175#music-metadata-management",
    );
    expect(await screen.findByText("track #175")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "返回详情" })).toHaveAttribute(
      "href",
      "/music/tracks/175",
    );
    await waitFor(() =>
      expect(document.activeElement).toHaveAttribute(
        "id",
        "metadata-panel-track-credits",
      ),
    );
    expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it("migrates legacy merge deep links to the matching inner content area", async () => {
    const trackMerge = renderRoute(
      "/settings?metadata=track-merge&artist=Olivia%20Rodrigo#music-metadata-management",
    );
    expect(await screen.findByTestId("version-merge-workspace")).toHaveTextContent(
      "track ·Olivia Rodrigo",
    );
    trackMerge.unmount();

    const album = renderRoute(
      "/settings?metadata=album-projects&album_name=GUTS&artist=Olivia%20Rodrigo#music-metadata-management",
    );
    expect(await screen.findByTestId("version-merge-workspace")).toHaveTextContent(
      "album ·Olivia Rodrigo · GUTS",
    );
    album.unmount();
  });

  it("prefills the manual track merge workspace from a detail deep link", async () => {
    renderRoute(
      "/settings?metadata=merge&merge_type=track&track_id=175&artist=Elton%20John&return_to=%2Fmusic%2Ftracks%2F175#music-metadata-management",
    );
    expect(await screen.findByTestId("version-merge-workspace")).toHaveTextContent(
      "track ·Elton John · · 175",
    );
    expect(screen.getByRole("link", { name: "返回详情" })).toHaveAttribute("href", "/music/tracks/175");
  });

  it("moves legacy genre and language links into the embedded metadata module", async () => {
    renderRoute("/settings?metadata=genre-health#genre-data-health");
    expect(await screen.findByTestId("genre-language-health")).toHaveTextContent("embedded:true");
    expect(screen.getByRole("tab", { name: /流派与语言/ })).toHaveAttribute("aria-selected", "true");
    await waitFor(() => expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalledTimes(1));
  });

  it("keeps artist identity deep links independent", async () => {
    renderRoute(
      "/settings?metadata=artist-identities&artist=Jolin%20Tsai#music-metadata-management",
    );
    expect(await screen.findByTestId("artist-identity")).toHaveTextContent(
      "Jolin Tsai",
    );
  });
});
