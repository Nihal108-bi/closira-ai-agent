"""
main.py — Closira AI Agent CLI.

Run a live conversation:
    python main.py

Run the automated demo (all 5 test scenarios):
    python main.py --demo

Options:
    --provider    anthropic | openai   (default: anthropic)
    --model       override the default model
    --debug       enable verbose logging
    --demo        run all test scenarios non-interactively
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap path so `src` imports work regardless of working directory
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

from src.agent import ClosiraAgent
from src.models.schemas import ConversationState
from src.utils.llm_client import create_llm_client
from src.utils.logger import configure_logging, EventLogger

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rich imports (graceful fallback if not installed)
# ---------------------------------------------------------------------------
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.markdown import Markdown
    from rich import print as rprint
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None  # type: ignore


# ---------------------------------------------------------------------------
# Demo scenarios (one per required test case)
# ---------------------------------------------------------------------------

DEMO_SCENARIOS = [
    {
        "name": "Scenario 1 — In-SOP Question",
        "description": "Customer asks about Botox prices. Expect accurate SOP answer.",
        "messages": [
            "Hi! What are your Botox prices?",
            "How long does it last?",
            "Great, can I book a consultation?",
        ],
    },
    {
        "name": "Scenario 2 — Out-of-Scope Question",
        "description": "Customer asks something not in the SOP. Expect gap detection + escalation offer.",
        "messages": [
            "Hello, do you offer laser hair removal?",
            "What about skin peels?",
        ],
    },
    {
        "name": "Scenario 3 — Escalation Trigger (Sentiment)",
        "description": "Customer expresses frustration. Expect immediate escalation.",
        "messages": [
            "I'm really unhappy with my last treatment here. It was absolutely terrible.",
        ],
    },
    {
        "name": "Scenario 4 — Lead Qualification",
        "description": "Customer engages through FAQ then completes qualification questions.",
        "messages": [
            "Hi, I'm interested in lip fillers.",
            "Yes, please — I'd love to know more.",
            "Lip fillers please.",
            "No, it would be my first time.",
            "I want to add a bit of volume and definition.",
        ],
    },
    {
        "name": "Scenario 5 — Full Session with Summary",
        "description": "End-to-end session culminating in a structured conversation summary.",
        "messages": [
            "Hello! What services do you offer?",
            "How much are fillers?",
            "Do you do evening appointments?",
            "Sure, I'd love to tell you more about what I'm after.",
            "Cheek fillers.",
            "Yes, I've had Botox before but never fillers.",
            "I want to restore some volume — I've lost a lot in my cheeks.",
        ],
    },
]


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def _print_banner() -> None:
    if RICH_AVAILABLE:
        console.print(
            Panel.fit(
                "[bold magenta]Closira AI Agent[/bold magenta]\n"
                "[dim]Powered by Bloom Aesthetics Clinic SOP[/dim]",
                border_style="magenta",
            )
        )
        console.print(
            "[dim]Type your message and press Enter. "
            "Commands: [bold]/summary[/bold] · [bold]/quit[/bold][/dim]\n"
        )
    else:
        print("=" * 60)
        print("  Closira AI Agent — Bloom Aesthetics Clinic")
        print("=" * 60)
        print("Commands: /summary · /quit\n")


def _print_user(message: str) -> None:
    if RICH_AVAILABLE:
        console.print(f"[bold cyan]You:[/bold cyan] {message}")
    else:
        print(f"You: {message}")


def _print_assistant(message: str, stage: str) -> None:
    stage_colours = {
        "faq": "green",
        "qualification": "yellow",
        "escalated": "red",
        "summary": "blue",
    }
    colour = stage_colours.get(stage, "white")
    if RICH_AVAILABLE:
        console.print(
            Panel(
                message,
                title=f"[{colour}]Bloom 🌸  [{stage.upper()}][/{colour}]",
                border_style=colour,
            )
        )
    else:
        print(f"\nBloom [{stage.upper()}]: {message}\n")


def _print_stage_change(stage: str) -> None:
    if RICH_AVAILABLE:
        console.print(f"\n[dim]── Stage: {stage.upper()} ──[/dim]\n")
    else:
        print(f"\n-- Stage: {stage.upper()} --\n")


def _print_scenario_header(scenario: dict) -> None:
    if RICH_AVAILABLE:
        console.rule(f"[bold yellow]{scenario['name']}[/bold yellow]")
        console.print(f"[dim]{scenario['description']}[/dim]\n")
    else:
        print("\n" + "=" * 60)
        print(f"  {scenario['name']}")
        print(f"  {scenario['description']}")
        print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Core run functions
# ---------------------------------------------------------------------------

def run_interactive(agent: ClosiraAgent) -> None:
    """Run a live interactive CLI session."""
    _print_banner()
    state = agent.new_session()
    print(f"Session ID: {state.session_id}\n")

    greeting = (
        "Hello! Welcome to Bloom Aesthetics Clinic. 🌸 "
        "I'm Bloom, your AI assistant. How can I help you today?"
    )
    _print_assistant(greeting, state.stage.value)
    state.add_assistant_message(greeting)

    while True:
        try:
            if RICH_AVAILABLE:
                console.print("[bold cyan]You:[/bold cyan] ", end="")
                user_input = input().strip()
            else:
                user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye! 👋")
            break

        if not user_input:
            continue

        # Built-in commands
        if user_input.lower() == "/quit":
            print("Goodbye! 👋")
            break
        if user_input.lower() == "/summary":
            summary = agent._summarizer.generate(state)
            print(agent._summarizer.format_for_display(summary))
            continue

        prev_stage = state.stage.value
        response, state, summary = agent.process(state, user_input)

        if state.stage.value != prev_stage:
            _print_stage_change(state.stage.value)

        _print_assistant(response, state.stage.value)

        if summary:
            # Summary was generated inline; session is done
            break


def run_demo(agent: ClosiraAgent) -> None:
    """Run all five test scenarios automatically."""
    if RICH_AVAILABLE:
        console.rule("[bold magenta]DEMO MODE — All 5 Test Scenarios[/bold magenta]")
    else:
        print("\n" + "=" * 60)
        print("  DEMO MODE — All 5 Test Scenarios")
        print("=" * 60)

    for scenario in DEMO_SCENARIOS:
        _print_scenario_header(scenario)
        state = agent.new_session()

        greeting = (
            "Hello! Welcome to Bloom Aesthetics Clinic. 🌸 "
            "I'm Bloom, your AI assistant. How can I help you today?"
        )
        _print_assistant(greeting, state.stage.value)
        state.add_assistant_message(greeting)

        for message in scenario["messages"]:
            time.sleep(0.3)   # pacing for readability
            _print_user(message)
            prev_stage = state.stage.value
            response, state, summary = agent.process(state, message)

            if state.stage.value != prev_stage:
                _print_stage_change(state.stage.value)

            _print_assistant(response, state.stage.value)

            # Stop demo for this scenario if escalated or summarised
            if state.stage.value in ("escalated", "summary"):
                break

        if RICH_AVAILABLE:
            console.print(f"\n[dim]Session {state.session_id} ended at stage: {state.stage.value}[/dim]\n")
        else:
            print(f"\nSession {state.session_id} ended at stage: {state.stage.value}\n")

        time.sleep(0.5)

    if RICH_AVAILABLE:
        console.rule("[bold green]Demo Complete[/bold green]")
    else:
        print("\n-- Demo Complete --")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Closira AI Customer Support Agent",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--provider",
        choices=["anthropic", "openai"],
        default="anthropic",
        help="LLM provider to use",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the default model (e.g. claude-3-5-haiku-20241022)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run all 5 demo scenarios non-interactively",
    )
    return parser.parse_args()


def load_sop() -> dict:
    sop_path = Path(__file__).parent / "config" / "sop.json"
    if not sop_path.exists():
        raise FileNotFoundError(f"SOP file not found at {sop_path}")
    with sop_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def main() -> None:
    args = parse_args()
    configure_logging(debug=args.debug)

    sop_data = load_sop()

    # Build LLM client
    client_kwargs: dict = {}
    if args.model:
        client_kwargs["model"] = args.model

    try:
        llm = create_llm_client(provider=args.provider, **client_kwargs)
    except EnvironmentError as exc:
        print(f"\n[ERROR] {exc}")
        print("Set your API key in the environment or in a .env file.")
        sys.exit(1)

    agent = ClosiraAgent(llm=llm, sop_data=sop_data)

    if args.demo:
        run_demo(agent)
    else:
        run_interactive(agent)


if __name__ == "__main__":
    main()
