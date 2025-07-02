from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, function_tool, RunContext
from livekit.plugins import (
    openai,
    noise_cancellation,
)

from budget_tools import BudgetSheetsManager

load_dotenv()


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="You are a helpful voice AI assistant.")
        self.budget_manager = BudgetSheetsManager()

    @function_tool()
    def add_transaction(self, context: RunContext, date: str, description: str, amount: float, transaction_type: str, category: str = ""):
        """Adds a new transaction to the budget. Date must be in YYYY-MM-DD format. Transaction type must be 'Income' or 'Expense'."""
        return self.budget_manager.add_transaction(date, description, amount, transaction_type, category)

    @function_tool()
    def edit_transaction(self, context: RunContext, row_index: int, date: str = None, description: str = None, amount: float = None, transaction_type: str = None, category: str = None):
        """Edits an existing transaction in the budget. Row index is 1-based. Only provide fields you want to change."""
        return self.budget_manager.edit_transaction(row_index, date, description, amount, transaction_type, category)

    @function_tool()
    def delete_transaction(self, context: RunContext, row_index: int):
        """Deletes a transaction from the budget. Row index is 1-based. Cannot delete header row (row 1)."""
        return self.budget_manager.delete_transaction(row_index)

    @function_tool()
    def modify_budget(self, context: RunContext, category: str, budget_limit: float):
        """Sets or updates the budget limit for a specific category."""
        return self.budget_manager.modify_budget(category, budget_limit)


async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        llm=openai.realtime.RealtimeModel(
            voice="coral"
        )
    )

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(
            # LiveKit Cloud enhanced noise cancellation
            # - If self-hosting, omit this parameter
            # - For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()

    await session.generate_reply(
        instructions="Greet the user and offer your assistance."
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
