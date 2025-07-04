from budget_tools import BudgetSheetsManager

def main():
    try:
        print("Creating BudgetSheetsManager instance...")
        manager = BudgetSheetsManager()
        print("Instance created successfully.")

        print("Available methods on BudgetSheetsManager instance:")
        print(dir(manager))

        print("\nCalling get_all_existing_categories()...")
        result = manager.get_all_existing_categories()
        print("Result:", result)

    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    main()
