"""
Basic usage example for AI Flow Architect

Before running:
1. Copy .env.example to .env and fill in your API keys
2. brain1 and brain2 must use models from different providers
"""

import asyncio
from ai_flow_architect import FlowArchitect


async def basic_example():
    """Basic workflow example"""
    print("=== Basic Example ===")

    # Brain #2 is mandatory and must use a different model
    architect = FlowArchitect(config={
        "brain1": "gpt-4o",
        "brain2": "claude-3-5-sonnet-20241022",
    })
    print("Framework initialized")

    user_input = "Design a user management system"
    print(f"User input: {user_input}")

    # Three phases run automatically: planning -> approval -> execution + arbitration
    print("\nStarting workflow...")
    result = await architect.run(user_input)

    print("\n=== Result ===")
    print(f"Status: {result['status']}")

    if result['status'] == 'success':
        audit = result.get('audit_result', {})
        score = audit.get('score', 'N/A')
        print(f"Quality score: {score}/100")
    elif result['status'] == 'needs_revision':
        print("Quality check failed. Suggestions:")
        for suggestion in result.get('revision_suggestions', []):
            print(f"  - {suggestion}")


async def expert_team_example():
    """Using a pre-configured expert team"""
    print("\n=== Expert Team Example ===")

    architect = FlowArchitect(config={
        "brain1": "gpt-4o",
        "brain2": "claude-3-5-sonnet-20241022",
    })
    print("Framework initialized")

    team_name = "web_development"
    user_input = "Build a blog platform"
    print(f"Team: {team_name}")
    print(f"User input: {user_input}")

    print("\nStarting workflow...")
    result = await architect.run_with_team(team_name, user_input)

    print("\n=== Result ===")
    print(f"Status: {result['status']}")


async def custom_blueprint_example():
    """Custom blueprint example (no AI calls, just data structure)"""
    print("\n=== Custom Blueprint Example ===")

    from ai_flow_architect.core.architect import Blueprint

    blueprint = Blueprint(
        task_id="custom_001",
        description="Data analysis pipeline",
        steps=[
            {
                "name": "Data collection",
                "expert": "evaluator",
                "task": "Collect and organize data sources",
                "prompt": "As an evaluator, analyze data requirements and identify sources...",
                "complexity": "medium",
            },
            {
                "name": "Data cleaning",
                "expert": "programmer",
                "task": "Clean and preprocess data",
                "prompt": "As a programmer, write data cleaning scripts...",
                "complexity": "high",
            },
            {
                "name": "Data analysis",
                "expert": "creative",
                "task": "Perform deep data analysis",
                "prompt": "As a creative analyst, discover valuable insights from data...",
                "complexity": "high",
            },
            {
                "name": "Report generation",
                "expert": "reviewer",
                "task": "Generate analysis report",
                "prompt": "As a reviewer, synthesize results into a final report...",
                "complexity": "medium",
            },
        ],
        experts=["evaluator", "programmer", "creative", "reviewer"],
        estimated_tokens=8000,
        status="draft",
    )

    print(f"Blueprint ID: {blueprint.task_id}")
    print(f"Description: {blueprint.description}")
    print(f"Steps: {len(blueprint.steps)}")

    for i, step in enumerate(blueprint.steps, 1):
        print(f"  {i}. {step['name']} ({step['expert']}, complexity: {step['complexity']})")


async def main():
    print("AI Flow Architect - Usage Examples")
    print("=" * 50)

    try:
        await basic_example()
        await expert_team_example()
        await custom_blueprint_example()

        print("\n" + "=" * 50)
        print("Examples complete")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
