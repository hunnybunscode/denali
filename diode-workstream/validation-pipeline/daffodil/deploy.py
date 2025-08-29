import os
import time

import boto3  # type: ignore
import typer  # type: ignore
from rich import print  # type: ignore
from rich.progress import Progress  # type: ignore
from rich.progress import SpinnerColumn  # type: ignore
from rich.progress import TextColumn  # type: ignore
from typing_extensions import Annotated  # type: ignore

# from pathlib import Path

NAMESPACE = os.getenv("NAMESPACE")

REALPATH = os.path.dirname(os.path.realpath(__file__))

app = typer.Typer()
cf = boto3.client("cloudformation")


def get_rich_status(status: str):
    if status == "CREATE_COMPLETE":
        return f"[bold green]:white_check_mark: {status}[/bold green]"
    elif status.endswith("IN_PROGRESS"):
        return f"[bold cyan]:information_source: {status}[/bold cyan]"
    else:
        return f"[bold red]:x: {status}[/bold red]"


@app.command()
def roles(
    template: Annotated[
        typer.FileText,
        typer.Option(prompt="Daffodil Roles CloudFormation template path"),
    ] = "target/daffodil-roles.yaml",
    iam_prefix: Annotated[str, typer.Option(prompt="IAM Prefix")] = "Cust",
    permission_boundary: Annotated[
        str,
        typer.Option(prompt="Permission Boundary"),
    ] = "Admin",
):
    cf.create_stack(
        StackName=f"daffodil-roles-{NAMESPACE}",
        TemplateBody=template.read(),
        Parameters=[
            {"ParameterKey": "iamprefixparam", "ParameterValue": iam_prefix},
            {
                "ParameterKey": "permissionboundary",
                "ParameterValue": permission_boundary,
            },
        ],
        Capabilities=["CAPABILITY_NAMED_IAM"],
    )

    print("\nStack creation status:")
    stack_info = cf.describe_stacks(StackName=f"daffodil-roles-{NAMESPACE}")["Stacks"][
        0
    ]
    status = stack_info["StackStatus"]
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description=f"{get_rich_status(status)}...", total=None)
        while (
            status and not status.endswith("COMPLETE") and not status.endswith("FAILED")
        ):
            time.sleep(2)
            stack_info = cf.describe_stacks(StackName=f"daffodil-roles-{NAMESPACE}")[
                "Stacks"
            ][0]
            if stack_info["StackStatus"] != status:
                status = stack_info["StackStatus"]
                progress.add_task(
                    description=f"{get_rich_status(status)}...",
                    total=None,
                )

    print(get_rich_status(status))


@app.callback()
def main():
    if not os.getenv("NAMESPACE"):
        os.environ["NAMESPACE"] = typer.prompt("Environment variable NAMESPACE not set")


if __name__ == "__main__":
    app()
