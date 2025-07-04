from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, function_tool, RunContext
from livekit.plugins import (
    openai,
    noise_cancellation,
)

from datetime import datetime, timedelta

import budget_tools
import budget_tools
print("budget_tools loaded from:", budget_tools.__file__)
from budget_tools import BudgetSheetsManager
print("BudgetSheetsManager loaded from:", BudgetSheetsManager.__module__)
print("Methods:", dir(BudgetSheetsManager))

manager = BudgetSheetsManager()
print(manager.get_all_existing_categories())



class ToolError(Exception):
    """Custom exception to signal tool execution errors to the agent framework."""
    pass


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="You are a helpful voice AI assistant.")
        try:
            self.budget_manager = BudgetSheetsManager()
            print("BudgetSheetsManager initialized successfully.")
            print("BudgetSheetsManager methods:", dir(self.budget_manager))
        except Exception as e:
            print(f"Error initializing BudgetSheetsManager: {e}")
            raise

    @function_tool()
    async def add_transaction(self, context: RunContext, date: str, description: str, amount: float, transaction_type: str, category: str = ""):
        """Adds a new transaction to the budget."""
        if date.lower() == "today":
            date = datetime.now().strftime("%Y-%m-%d")
        elif date.lower() == "yesterday":
            date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        if category:
            existing_categories_response = self.budget_manager.get_all_existing_categories()
            if existing_categories_response["status"] == "error":
                return existing_categories_response
            existing_categories = [c.lower() for c in existing_categories_response["categories"]]

            if category.lower() not in existing_categories:
                return {
                    "status": "error",
                    "message": f"Category '{category}' does not exist. Would you like to create it or choose an existing category? Existing categories: {', '.join(existing_categories_response['categories'])}."
                }

        return self.budget_manager.add_transaction(date, description, amount, transaction_type, category)

    @function_tool()
    async def edit_transaction(self, context: RunContext, row_index: int, date: str = None, description: str = None, amount: float = None, transaction_type: str = None, category: str = None):
        """Edits an existing transaction in the budget."""
        if date:
            if date.lower() == "today":
                date = datetime.now().strftime("%Y-%m-%d")
            elif date.lower() == "yesterday":
                date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        print(f"DEBUG: edit_transaction called with row_index={row_index}, date={date}, description={description}, amount={amount}, transaction_type={transaction_type}, category={category}")
        return self.budget_manager.edit_transaction(row_index, date, description, amount, transaction_type, category)

    @function_tool()
    async def delete_transaction(self, context: RunContext, description: str = None, category: str = None, amount: float = None, date: str = None):
        """Deletes a transaction from the budget based on matching criteria."""
        all_transactions_response = self.budget_manager.get_all_transactions()
        if all_transactions_response["status"] == "error":
            return all_transactions_response

        all_transactions = all_transactions_response["transactions"]
        matching_transactions = []

        for t in all_transactions:
            match = True
            if description and description.lower() not in t['description'].lower():
                match = False
            if category and category.lower() not in t['category'].lower():
                match = False
            if amount and float(amount) != float(t['amount']):
                match = False
            if date and date != t['date']:
                match = False

            if match:
                matching_transactions.append(t)

        if len(matching_transactions) == 0:
            return {"status": "error", "message": "No matching transaction found."}
        elif len(matching_transactions) > 1:
            return {"status": "ambiguous", "message": f"Multiple transactions match your criteria. Please be more specific. Matching transactions: {matching_transactions}"}
        else:
            transaction_to_delete = matching_transactions[0]
            row_index = transaction_to_delete['_row_index']
            return self.budget_manager.delete_transaction(row_index)

    @function_tool()
    async def modify_budget(self, context: RunContext, category: str, budget_limit: float):
        """Sets or updates the budget limit for a specific category."""
        return self.budget_manager.modify_budget(category, budget_limit)

    @function_tool()
    async def get_transactions(self, context: RunContext, date: str = None, description: str = None, amount: float = None, transaction_type: str = None, category: str = None):
        """Retrieves transactions based on optional filters."""
        import asyncio
        return await asyncio.to_thread(self.budget_manager.get_all_transactions())


async def entrypoint(ctx: agents.JobContext):
    try:
        print("Starting entrypoint")

        session = AgentSession(
            llm=openai.realtime.RealtimeModel(
                voice="coral"
            )
        )

        await ctx.connect()
        print("Connected to JobContext")

        await session.start(
            room=ctx.room,
            agent=Assistant(),
            room_input_options=RoomInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
        )
        print("Session started")

        await session.generate_reply(
            instructions="Greet the user and offer your assistance."
        )
        print("Generated initial reply")

    except Exception as e:
        print(f"Exception in entrypoint: {e}")
        raise


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
