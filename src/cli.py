import json
import click
from .pipeline.generate import generate as run_generate


@click.group()
def cli():
    """Parametric 3D-printed bag/fabric/handle generator."""
    pass


@cli.command()
@click.option("--config", required=True, type=click.Path(exists=True))
@click.option("--out", default="output/", type=click.Path())
def generate(config, out):
    written = run_generate(config, out)
    click.echo(json.dumps(written, indent=2))


@cli.command()
def options():
    opts = {
        "body.shape_profile": ["rectangular", "rounded_rectangle", "trapezoidal"],
        "fabric.link_type": ["ring", "pyramid", "hybrid"],
        "connector.type": ["loop_hinge", "socket_peg", "fused_row"],
        "solids.bottom_panel.foot_style": ["none", "rounded_feet", "rail"],
        "handles.end_reinforcement": ["sleeve", "loop", "flat_tab"],
        "export.formats": ["stl", "3mf", "step (planned)"],
    }
    click.echo(json.dumps(opts, indent=2))


if __name__ == "__main__":
    cli()
