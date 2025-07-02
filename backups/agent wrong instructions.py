from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, function_tool, RunContext, ToolError
from livekit.plugins import (
    openai,
    noise_cancellation,
)

from datetime import datetime, timedelta

from budget_tools import BudgetSheetsManager

load_dotenv()


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful voice AI assistant. Your interface with users will be voice. "
                "You should use short and concise responses, and avoiding usage of unpronounceable punctuation. "
                "You were created as a demo to showcase the capabilities of LiveKit's agents framework. "
                "If a tool call fails or returns an error message, you must clearly communicate that error message to the user."
            )
        )
        self.budget_manager = BudgetSheetsManager()

@function_tool()
def add_transaction(self, context: RunContext, date: str, description: str, amount: float, transaction_type: str, category: str = ""):
    """Adds a new transaction to the budget. Date must be in YYYY-MM-DD format, or can be 'today' or 'yesterday'. Transaction type must be 'Income' or 'Expense'. The category must be an existing category from the budget. If the category does not exist, ask the user to provide an existing category."""
    
    # Interpret relative dates
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
            print(f"DEBUG: Raising ToolError for invalid category: {category}")
            raise ToolError(
                f"Category '{category}' does not exist. Would you like to create it? "
                f"If so, please specify if it's an Income or Expense category and a projected amount. "
                f"Existing categories: {', '.join(existing_categories_response['categories'])}."
            )

    return self.budget_manager.add_transaction(date, description, amount, transaction_type, category)
    @function_tool()
    def edit_transaction(self, context: RunContext, row_index: int, date: str = None, description: str = None, amount: float = None, transaction_type: str = None, category: str = None):
        """Edits an existing transaction in the budget. Row index is 1-based. Only provide fields you want to change."""
        # Interpret relative dates if provided
        if date:
            if date.lower() == "today":
                date = datetime.now().strftime("%Y-%m-%d")
            elif date.lower() == "yesterday":
                date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        print(f"DEBUG: edit_transaction called with row_index={row_index}, date={date}, description={description}, amount={amount}, transaction_type={transaction_type}, category={category}")
        return self.budget_manager.edit_transaction(row_index, date, description, amount, transaction_type, category)

    @function_tool()
    def delete_transaction(self, context: RunContext, description: str = None, category: str = None, amount: float = None, date: str = None):
        """Deletes a transaction from the budget based on its description, category, amount, or date. The AI should use these parameters to find the specific transaction to delete. If multiple transactions match, the AI should ask for clarification."""
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
            # The AI should ask for clarification if multiple transactions match
            return {"status": "ambiguous", "message": f"Multiple transactions match your criteria. Please be more specific. Matching transactions: {matching_transactions}"}
        else:
            # Exactly one transaction matches, proceed with deletion
            transaction_to_delete = matching_transactions[0]
            row_index = transaction_to_delete['_row_index']
            return self.budget_manager.delete_transaction(row_index)

    @function_tool()
    def modify_budget(self, context: RunContext, category: str, budget_limit: float):
        """Sets or updates the budget limit for a specific category."""
        return self.budget_manager.modify_budget(category, budget_limit)

    @function_tool()
    async def get_transactions(self, context: RunContext, date: str = None, description: str = None, amount: float = None, transaction_type: str = None, category: str = None):
        """Retrieves transactions from the budget based on optional filters. Date can be a specific date (YYYY-MM-DD) or a range (e.g., 'last week', 'this month')."""
        # The budget_tools.py get_all_transactions returns all, we'll filter here or in budget_tools if needed
        # For now, let's assume get_all_transactions is sufficient and we'll filter in the agent if necessary
        # Or, we can enhance get_all_transactions to accept filters.
        # For simplicity, let's just return all for now and let the LLM filter or ask for more specific criteria.
        import asyncio
        return await asyncio.to_thread(self.budget_manager.get_all_transactions)

    @function_tool()
    async def create_category(self, context: RunContext, category: str, projected_amount: float, category_type: str):
        """Creates a new budget category with a projected amount and type (Income or Expense). This tool should only be called after the user explicitly confirms they want to create a new category, and after the agent has confirmed the category does not already exist."""
        import asyncio
        return await asyncio.to_thread(self.budget_manager.create_category, category, projected_amount, category_type)


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

    await session.generate_reply()


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
