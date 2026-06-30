from pathlib import Path


def print_summary(results, archive_summary, csv_report, history_db):
    indexed = []
    unknown = []
    canonical = []
    other = []

    indexed_states = {
        "Submitted and indexed",
        "Indexed, not submitted in sitemap",
    }

    for result in results:
        coverage = result.coverage or "Unknown"

        if coverage in indexed_states:
            indexed.append(result)
        elif coverage == "URL is unknown to Google":
            unknown.append(result)
        elif "canonical" in coverage.lower():
            canonical.append(result)
        else:
            other.append(result)

    print()
    print("===========================================")
    print("SUMMARY")
    print("===========================================")
    print()

    print(f"Pages inspected:        {len(results)}")
    print(f"Indexed:                {len(indexed)}")
    print(f"Unknown to Google:      {len(unknown)}")
    print(f"Canonical issues:       {len(canonical)}")
    print(f"Other issues:           {len(other)}")

    if unknown or canonical or other:
        print()
        print("Needs Attention")
        print("----------------")

        for result in unknown:
            print(f"• {Path(result.url).name}")
            print("    URL is unknown to Google")

        for result in canonical:
            print(f"• {Path(result.url).name}")
            print(f"    {result.coverage}")

        for result in other:
            print(f"• {Path(result.url).name}")
            print(f"    {result.coverage or 'Unknown'}")

    print()
    print("CSV report written to:")
    print(f"  {csv_report}")

    print()
    print("History database updated:")
    print(f"  {history_db}")
    print(f"  Run ID: {archive_summary['run_id']}")
    changed = "yes" if archive_summary["changed"] else "no"
    print(f"  Changed since previous run: {changed}")

    if archive_summary["changes"]:
        print()
        print("Changed URLs")
        print("------------")

        for change in archive_summary["changes"][:10]:
            print(f"• {Path(change['url']).name}")
            print(f"    {change['previous_coverage']} -> {change['current_coverage']}")

        remaining = len(archive_summary["changes"]) - 10
        if remaining > 0:
            print(f"    ...and {remaining} more")
