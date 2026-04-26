#!/usr/bin/env python3
"""CLI entry point for the Multifamily Deal Analyzer."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def run_pipeline(args):
    from config import WESTERN_US_STATES
    from models.database import init_db, get_session, upsert_deal
    from underwriting.engine import underwrite
    from underwriting.assumptions import get_default_assumptions
    from excel.generator import generate_excel

    init_db()
    assumptions = get_default_assumptions()
    states = args.states.split(",") if args.states else WESTERN_US_STATES[:5]

    console.print(f"\n[bold blue]🏢 Multifamily Deal Analyzer[/bold blue]")
    console.print(f"Source: [bold]{args.source}[/bold] | States: {', '.join(states)} | Max: ${args.max_price:,.0f}\n")

    # Load scraper
    if args.source == "mock":
        from scrapers.mock import MockScraper
        scraper = MockScraper()
    elif args.source == "crexi":
        from scrapers.crexi import CrexiScraper
        scraper = CrexiScraper()
    elif args.source == "zillow":
        from scrapers.zillow import ZillowScraper
        scraper = ZillowScraper()
    else:
        console.print("[red]Unknown source. Use: mock, crexi, zillow[/red]")
        sys.exit(1)

    results_table = Table(
        "Address", "State", "Units", "Price", "Cap Rate", "CoC Y1", "DSCR", "5yr IRR",
        title="🏢 Deal Pipeline — Ranked by Cap Rate",
        box=box.ROUNDED,
        show_lines=True,
    )

    session = get_session()
    deals = []

    with console.status("Fetching listings..."):
        props = list(scraper.fetch(states, args.min_units, args.max_units, args.max_price, args.limit))

    console.print(f"Found [bold green]{len(props)}[/bold green] listings. Underwriting...\n")

    for prop in props:
        try:
            r = underwrite(prop, assumptions)
            deals.append((prop, r))
        except Exception as e:
            console.print(f"[dim]Skip {prop.address}: {e}[/dim]")

    # Sort by cap rate descending
    deals.sort(key=lambda x: x[1].going_in_cap_rate, reverse=True)

    excel_count = 0
    for prop, r in deals:
        cap_color = "green" if r.going_in_cap_rate >= 0.06 else "yellow"
        coc_color = "green" if r.coc_y1 >= 0.07 else "yellow"
        dscr_color = "green" if r.dscr_y1 >= 1.25 else "red"
        irr_str = f"{r.irr_5yr:.1%}" if r.irr_5yr else "—"

        results_table.add_row(
            f"{prop.address[:30]}",
            prop.state,
            str(prop.units),
            f"${prop.purchase_price:,.0f}",
            f"[{cap_color}]{r.going_in_cap_rate:.1%}[/{cap_color}]",
            f"[{coc_color}]{r.coc_y1:.1%}[/{coc_color}]",
            f"[{dscr_color}]{r.dscr_y1:.2f}x[/{dscr_color}]",
            irr_str,
        )

        # Save to DB
        upsert_deal(session, {
            "address": prop.address, "city": prop.city, "state": prop.state,
            "units": prop.units, "purchase_price": prop.purchase_price,
            "listing_url": prop.listing_url, "source": prop.source,
            "scraped_at": prop.scraped_at, "status": "pipeline",
            "gpr": r.gpr, "noi": r.noi, "going_in_cap_rate": r.going_in_cap_rate,
            "loan_amount": r.loan_amount, "equity_invested": r.equity_invested,
            "annual_ds": r.annual_ds_io, "coc_y1": r.coc_y1, "dscr_y1": r.dscr_y1,
            "irr_5yr": r.irr_5yr, "irr_10yr": r.irr_10yr,
            "uw_assumptions_json": assumptions.model_dump(),
        })

        # Generate Excel for top deals
        if args.excel and excel_count < args.excel_limit:
            try:
                path = generate_excel(prop, assumptions, r)
                console.print(f"  [dim]Excel: {path.name}[/dim]")
                excel_count += 1
            except Exception as e:
                console.print(f"  [red]Excel error: {e}[/red]")

    console.print(results_table)
    console.print(f"\n[bold]Saved {len(deals)} deals to database.[/bold]")
    if args.excel:
        console.print(f"Generated {excel_count} Excel files in ./outputs/")
    session.close()


def main():
    parser = argparse.ArgumentParser(description="Multifamily Deal Analyzer CLI")
    sub = parser.add_subparsers(dest="cmd")

    run_p = sub.add_parser("run", help="Scrape and underwrite listings")
    run_p.add_argument("--source", default="mock", choices=["mock", "crexi", "zillow"],
                        help="Data source (default: mock)")
    run_p.add_argument("--states", default="CA,OR,WA,AZ,CO",
                        help="Comma-separated state codes (default: CA,OR,WA,AZ,CO)")
    run_p.add_argument("--min-units", type=int, default=3)
    run_p.add_argument("--max-units", type=int, default=10)
    run_p.add_argument("--max-price", type=float, default=2_000_000)
    run_p.add_argument("--limit", type=int, default=20, help="Max listings to fetch")
    run_p.add_argument("--excel", action="store_true", help="Generate Excel files")
    run_p.add_argument("--excel-limit", type=int, default=5, help="Max Excel files to generate")

    app_p = sub.add_parser("app", help="Launch the Streamlit web app")

    args = parser.parse_args()

    if args.cmd == "run":
        run_pipeline(args)
    elif args.cmd == "app":
        import subprocess
        app_path = Path(__file__).parent / "app" / "Home.py"
        subprocess.run(["streamlit", "run", str(app_path)], check=True)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
