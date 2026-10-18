import argparse
import json

from . import service
from .render import documents


def main():
    parser = argparse.ArgumentParser(description="Conduit SQL reporting commands")
    sub = parser.add_subparsers(dest="action", required=True)
    submit = sub.add_parser("submit")
    submit.add_argument(
        "template", choices=["customer_statement", "product_sales", "monthly_sales"]
    )
    submit.add_argument("--start", default="2026-01-01")
    submit.add_argument("--end", default="2027-01-01")
    submit.add_argument("--customer", type=int)
    submit.add_argument("--bulk", action="store_true")
    submit.add_argument("--key", help="UUID retry identity")
    status = sub.add_parser("status")
    status.add_argument("run_id")
    evidence = sub.add_parser("evidence")
    evidence.add_argument("request_id")
    replay = sub.add_parser("replay")
    replay.add_argument("request_id")
    replay.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.action == "submit":
        print(
            service.submit(
                args.template,
                args.start,
                args.end,
                args.customer,
                bulk=args.bulk,
                submission_key=args.key,
            )
        )
    elif args.action == "status":
        print(json.dumps(service.progress(args.run_id), default=str, indent=2))
    elif args.action == "evidence":
        print(json.dumps(service.evidence(args.request_id), default=str, indent=2))
    else:
        from pathlib import Path

        report = service.replay(args.request_id)
        if report is None:
            raise SystemExit("Unknown prepared request")
        Path(args.output).write_bytes(documents(report)["html"])


if __name__ == "__main__":
    main()
