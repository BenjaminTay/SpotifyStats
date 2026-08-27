import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { VersionMergeSection } from "@/features/settings/components/VersionMergeSection";

const { versionMergeMock } = vi.hoisted(() => ({
  versionMergeMock: {
    groups: [
      {
        group_id: 1,
        canonical_name: "GUTS",
        artist_name: "Olivia Rodrigo",
        artist_id: 1,
        primary_album_id: 10,
        primary_album_name: "GUTS",
        member_count: 2,
        scope: "release",
        is_manual: true,
      },
    ],
    groupsLoading: false,
    fetchGroups: vi.fn().mockResolvedValue([]),
    trackGroups: [
      {
        group_id: 2,
        canonical_name: "Style",
        primary_track_id: 101,
        primary_track_name: "Style",
        primary_album_id: 10,
        artist_name: "Taylor Swift",
        member_count: 2,
        scope: "recording",
        is_manual: 1,
        created_at: "2026-08-26",
      },
    ],
    trackGroupsLoading: false,
    fetchTrackGroups: vi.fn().mockResolvedValue([]),
    detectGroups: vi.fn().mockResolvedValue([]),
    applyDetected: vi
      .fn()
      .mockResolvedValue({ created_count: 0, skipped_count: 0 }),
    fetchCollaborationCandidates: vi.fn().mockResolvedValue([]),
    searchTracks: vi.fn().mockResolvedValue([
      {
        track_id: 101,
        track_name: "Style",
        artist_name: "Taylor Swift",
        album_name: "1989",
        spotify_track_id: "spotify-101",
        play_count: 20,
        first_play_date: null,
        last_play_date: null,
        effective_artist_names: ["Taylor Swift"],
      },
      {
        track_id: 102,
        track_name: "Style (Taylor's Version)",
        artist_name: "Taylor Swift",
        album_name: "1989 (Taylor's Version)",
        spotify_track_id: "spotify-102",
        play_count: 15,
        first_play_date: null,
        last_play_date: null,
        effective_artist_names: ["Taylor Swift"],
      },
    ]),
    confirmTrackCandidate: vi
      .fn()
      .mockResolvedValue({ status: "ok", member_count: 2 }),
    rebuildAlbumProjects: vi.fn(),
    getGroupMembers: vi.fn().mockResolvedValue([]),
    getTrackGroupMembers: vi.fn().mockResolvedValue([
      {
        track_id: 101,
        track_name: "Style",
        album_id: 10,
        artist_name: "Taylor Swift",
        is_primary: 1,
      },
      {
        track_id: 102,
        track_name: "Style (Taylor's Version)",
        album_id: 11,
        artist_name: "Taylor Swift",
        is_primary: 0,
      },
    ]),
    getUngroupedAlbums: vi.fn().mockResolvedValue([]),
    compareAlbums: vi.fn(),
    getAlbumTypes: vi.fn(),
    createGroup: vi.fn(),
    confirmAlbumRelation: vi.fn(),
    updateMembers: vi.fn(),
    setPrimary: vi.fn(),
    deleteGroup: vi.fn(),
    updateTrackMembers: vi.fn(),
    setPrimaryTrack: vi.fn(),
    deleteTrackGroup: vi.fn(),
    fetchCanonicalTrackEvents: vi.fn().mockResolvedValue([]),
    mergeCanonicalTracks: vi.fn().mockResolvedValue({
      status: "ok",
      canonical_track_id: 101,
      affected_canonical_track_ids: [102],
    }),
    splitCanonicalTrack: vi.fn(),
  },
}));

vi.mock("@/hooks/useSettings", () => ({
  useVersionMerge: () => versionMergeMock,
}));

describe("VersionMergeSection unified workspace", () => {
  beforeEach(() => vi.clearAllMocks());

  it("keeps object type above one shared operation tab set", () => {
    render(<VersionMergeSection />);

    expect(screen.queryByRole("heading", { name: "归并与版本" })).not.toBeInTheDocument();
    expect(screen.getAllByText("自动检测")).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "自动检测" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "已保存分组" })).toHaveLength(
      1,
    );
    expect(screen.getAllByRole("button", { name: "手动创建" })).toHaveLength(1);
    const objectTypes = screen.getByRole("radiogroup", {
      name: "归并对象类型",
    });
    expect(
      within(objectTypes).getByRole("radio", { name: /歌曲归并/ }),
    ).toHaveAttribute("aria-checked", "true");
    expect(
      screen.getByRole("radiogroup", { name: "歌曲归并生效层级" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("radio", { name: /L2 · 同一录音/ }),
    ).toHaveAttribute("aria-checked", "true");

    fireEvent.click(
      within(objectTypes).getByRole("radio", { name: /专辑归并/ }),
    );
    expect(
      screen.getByRole("radiogroup", { name: "专辑归并生效层级" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("曲目重叠率")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /L3 · 作品版本/ })).toBeDisabled();
  });

  it("labels saved items and supports selecting two tracks with an explicit merge level", async () => {
    render(<VersionMergeSection initialObjectType="track" />);

    const objectTypes = screen.getByRole("radiogroup", {
      name: "归并对象类型",
    });
    fireEvent.click(screen.getByRole("button", { name: "已保存分组" }));
    expect(screen.getByText("Style")).toBeInTheDocument();
    expect(screen.getByText("L2 同一录音")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Style 封面" })).toHaveAttribute(
      "src",
      "/covers/albums/10.jpg",
    );
    fireEvent.click(screen.getByRole("button", { name: "查看成员" }));
    expect(await screen.findAllByText(/Taylor Swift · #10[12]/)).toHaveLength(2);
    expect(
      screen.getByRole("img", { name: "Style (Taylor's Version) 封面" }),
    ).toHaveAttribute("src", "/covers/albums/11.jpg");

    fireEvent.click(screen.getByRole("button", { name: "手动创建" }));
    expect(
      within(objectTypes).getByRole("radio", { name: /歌曲归并/ }),
    ).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("选择歌曲")).toBeInTheDocument();

    const search = screen.getByLabelText("搜索要归并的歌曲");
    fireEvent.change(search, { target: { value: "Style" } });
    await waitFor(() =>
      expect(versionMergeMock.searchTracks).toHaveBeenCalledWith("Style"),
    );
    fireEvent.click(
      (await screen.findByText(/#101/)).closest("button") as HTMLButtonElement,
    );
    fireEvent.change(search, { target: { value: "Style" } });
    fireEvent.click(
      (await screen.findByText(/#102/)).closest("button") as HTMLButtonElement,
    );
    fireEvent.click(screen.getByRole("button", { name: /下一步：配置规则/ }));
    expect(screen.queryByRole("radio", { name: /L1 · 具体曲目/ })).not.toBeInTheDocument();
    expect(
      screen.getByRole("radio", { name: /L2 · 同一录音/ }),
    ).toHaveAttribute("aria-checked", "true");
    fireEvent.click(screen.getByRole("radio", { name: /L3 · 同一作品/ }));
    fireEvent.click(screen.getByRole("button", { name: /下一步：确认保存/ }));
    fireEvent.click(screen.getByRole("button", { name: /保存歌曲分组/ }));
    await waitFor(() =>
      expect(versionMergeMock.confirmTrackCandidate).toHaveBeenCalledWith(
        101,
        102,
        "composition",
      ),
    );

    fireEvent.click(
      within(objectTypes).getByRole("radio", { name: /专辑归并/ }),
    );
    expect(screen.getByText("选择专辑")).toBeInTheDocument();
    expect(screen.getByText("配置规则")).toBeInTheDocument();
  });

  it("does not expose L1 or synthetic base identity correction", () => {
    render(<VersionMergeSection initialObjectType="track" />);

    expect(screen.queryByText("高级：基础身份纠错")).not.toBeInTheDocument();
    expect(screen.queryByText(/执行基础身份合并/)).not.toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /歌曲归并/ })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /L2 · 同一录音/ })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /L3 · 同一作品/ })).toBeInTheDocument();
  });
});
