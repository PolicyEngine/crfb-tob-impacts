export type RoadmapStatus = "complete" | "gate" | "planned" | "blocked";

export type RoadmapIcon =
  | "package"
  | "flask"
  | "boxes"
  | "upload"
  | "git"
  | "shield"
  | "play";

export type RoadmapStep = {
  id: string;
  step: string;
  title: string;
  status: RoadmapStatus;
  icon: RoadmapIcon;
  outcome: string;
  gate: string;
  logTarget: string;
};

export const reproducibilityRoadmap = {
  lastUpdated: "May 22, 2026",
  currentGate:
    "The selected full-H5 reform panel is complete. Remaining work is post-H5 review, dashboard publication, and the future policyengine.py/HF bundle path.",
  currentNotes: [
    "Options 1-12 have 276/276 exact full reform H5 cells in R2 for 2026-2035 and every fifth year from 2040-2100.",
    "The current production run is reproducible from recorded SHAs, manifests, R2 URIs, and worker metadata, but it is not yet exposed through a policyengine.py bundle.",
    "Reform workers produce raw reform H5s plus metadata. Aggregate review is a separate MicroSeries/MicroDF-only step.",
  ],
  flow: [
    "Published stack",
    "Sentinel baselines",
    "Sharded baseline rebuild",
    "Durable HF release",
    "policyengine.py bundle",
    "Clean hash verification",
    "Reform H5 production",
  ],
  logTargets: [
    {
      label: "Version ledger",
      target: "results/production_logs/crfb_version_ledger.json",
    },
    {
      label: "Sentinel QA",
      target: "results/production_logs/sentinel_baseline_report.csv",
    },
    {
      label: "Release manifest",
      target: "results/production_logs/long_run_release_manifest.json",
    },
    {
      label: "Bundle verification",
      target: "results/production_logs/policyengine_py_bundle_verification.json",
    },
    {
      label: "Reform raw H5 metadata",
      target: "reform_raw_h5/year=YYYY/reform=OPTION/metadata.json",
    },
  ],
  steps: [
    {
      id: "resolve-input-stack",
      step: "01",
      title: "Resolve published input stack",
      status: "gate",
      icon: "package",
      outcome:
        "Pin the latest published policyengine.py bundle and matching policyengine-us and policyengine-us-data revisions before any production rebuild.",
      gate:
        "Version ledger shows the bundle, model runtime, source 2024 Enhanced CPS, and long-run builder inputs agree.",
      logTarget: "results/production_logs/crfb_version_ledger.json",
    },
    {
      id: "sentinel-baselines",
      step: "02",
      title: "Run sentinel baselines",
      status: "planned",
      icon: "flask",
      outcome:
        "Build 2026, 2070, 2075, and 2100 first against the resolved stack.",
      gate:
        "Trustees targets hit, support gates pass, baseline facts are sane, and business-income fields do not explode.",
      logTarget: "results/production_logs/sentinel_baseline_report.csv",
    },
    {
      id: "parallel-baseline",
      step: "03",
      title: "Parallel baseline rebuild",
      status: "planned",
      icon: "boxes",
      outcome:
        "After sentinel approval, rebuild annual 2026-2100 H5s using sharded workers aimed at a 30-45 minute wall-time target.",
      gate:
        "Exactly 75 H5s and sidecars complete with per-year validation and no failed shard.",
      logTarget: "results/production_logs/baseline_shard_manifest.json",
    },
    {
      id: "publish-release",
      step: "04",
      title: "Publish durable data release",
      status: "planned",
      icon: "upload",
      outcome:
        "Merge shard outputs, hash every H5, write release metadata, and publish to a durable Hugging Face revision.",
      gate:
        "Release manifest and TRO record the exact HF revision, hashes, builder SHA, and target years.",
      logTarget: "results/production_logs/long_run_release_manifest.json",
    },
    {
      id: "bundle-policyengine-py",
      step: "05",
      title: "Bundle into policyengine.py",
      status: "planned",
      icon: "git",
      outcome:
        "Refresh the policyengine.py release bundle so the public API resolves the same policyengine-us runtime and long-run HF revision.",
      gate:
        "Bundle manifest pins the rebuilt long-run data and the intended policyengine-us release.",
      logTarget: "policyengine.py release bundle PR and us.json manifest",
    },
    {
      id: "clean-verification",
      step: "06",
      title: "Clean bundle verification",
      status: "planned",
      icon: "shield",
      outcome:
        "Install policyengine.py cleanly, resolve sentinel years through the bundle path, and compare H5 hashes to the published release.",
      gate:
        "2026, 2070, 2075, and 2100 hash-match the release and pass MicroSeries/MicroDF baseline QA.",
      logTarget:
        "results/production_logs/policyengine_py_bundle_verification.json",
    },
    {
      id: "reform-h5-production",
      step: "07",
      title: "Launch reform H5 production",
      status: "complete",
      icon: "play",
      outcome:
        "Run reform workers from the documented v2 populace/TR2026 stack. Each worker saves raw reform H5 plus metadata; aggregate tables are derived afterward.",
      gate:
        "All current static selected-year cells and behavioral endpoints complete in R2. No aggregation uses raw household weights directly.",
      logTarget: "reform_raw_h5/year=YYYY/reform=OPTION/metadata.json",
    },
  ] satisfies RoadmapStep[],
};
