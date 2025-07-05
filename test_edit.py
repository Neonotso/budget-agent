from budget_tools import BudgetSheetsManager

manager = BudgetSheetsManager()

# Step 1: Print all current transactions (to find a valid row index)
transactions_result = manager.get_all_transactions()
if transactions_result["status"] != "success":
    print("Error retrieving transactions:", transactions_result["message"])
    exit()

transactions = transactions_result["transactions"]
for t in transactions:
    print(t)

# Step 2: Pick a valid row index to test an update
if transactions:
    test_row_index = transactions[0]['_row_index']  # Take the first transaction
    print(f"\nAttempting to edit row {test_row_index}...\n")

    edit_result = manager.edit_transaction(
        row_index=test_row_index,
        description="🧪 Test Edit",
        amount=123.45
    )
    print(edit_result)

    # Step 3: Reprint the updated row to confirm
    updated_result = manager.get_all_transactions()
    updated_transactions = updated_result["transactions"]
    for t in updated_transactions:
        if t['_row_index'] == test_row_index:
            print("\n✅ Updated Transaction:", t)
else:
    print("No transactions found to test editing.")

