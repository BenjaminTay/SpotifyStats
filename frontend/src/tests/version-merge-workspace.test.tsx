import { fireEvent, render, screen, within } from "@testing-library/react";
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
    detectGroups: vi.fn().mockResolvedValue([]),
    applyDetected: vi.fn().mockResolvedValue({ created_count: 0, skipped_count: 0 }),
    fetchCollaborationCandidates: vi.fn().mockResolvedValue([]),
    confirmTrackCandidate: vi.fn(),
    rebuildAlbumProjects: vi.fn(),
    getGroupMembers: vi.fn().mockResolvedValue([]),
    getUngroupedAlbums: vi.fn().mockResolvedValue([]),
    compareAlbums: vi.fn(),
    getAlbumTypes: vi.fn(),
    createGroup: vi.fn(),
    confirmAlbumRelation: vi.fn(),
    updateMembers: vi.fn(),
    setPrimary: vi.fn(),
    deleteGroup: vi.fn(),
  },
}));

vi.mock("@/hooks/useSettings", () => ({
  useVersionMerge: () => versionMergeMock,
}));

describe("VersionMergeSection unified workspace", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders one operation tab set and keeps album-only controls in advanced options", () => {
    render(<VersionMergeSection />);

    expect(screen.getByRole("heading", { name: "归并与版本" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "自动检测" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "已保存分组" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "手动创建" })).toHaveLength(1);
    expect(screen.getByText("歌曲归并", { selector: "[data-slot=badge], span" })).toBeInTheDocument();

    const advanced = screen.getByText("专辑版本高级选项").closest("details");
    expect(advanced).not.toHaveAttribute("open");
    fireEvent.click(screen.getByText("专辑版本高级选项"));
    expect(advanced).toHaveAttribute("open");
    expect(within(advanced as HTMLElement).getByLabelText("重叠率阈值")).toBeInTheDocument();
    expect(within(advanced as HTMLElement).getByRole("button", { name: "重建" })).toBeInTheDocument();
  });

  it("labels saved items and asks for object type only inside manual creation", () => {
    render(<VersionMergeSection initialObjectType="track" />);

    expect(screen.queryByRole("radiogroup", { name: "归并对象类型" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "已保存分组" }));
    expect(screen.getByText("GUTS")).toBeInTheDocument();
    expect(screen.getByText("专辑版本", { selector: "[data-slot=badge]" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "手动创建" }));
    const objectTypes = screen.getByRole("radiogroup", { name: "归并对象类型" });
    expect(within(objectTypes).getByRole("radio", { name: /歌曲归并/ })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("按稳定候选确认歌曲关系")).toBeInTheDocument();

    fireEvent.click(within(objectTypes).getByRole("radio", { name: /专辑版本/ }));
    expect(screen.getByText("选择专辑")).toBeInTheDocument();
    expect(screen.getByText("配置规则")).toBeInTheDocument();
  });
});
