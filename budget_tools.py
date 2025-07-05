import os
from dotenv import load_dotenv
load_dotenv() # load from .env file

from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

class BudgetSheetsManager:
    def __init__(self):
        self.creds = self._get_credentials()
        self.service = build("sheets", "v4", credentials=self.creds)
        self.spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID") or self._get_spreadsheet_id()
        print(self.spreadsheet_id)

        if not self.spreadsheet_id:
            raise ValueError("GOOGLE_SPREADSHEET_ID is not set in environment")

    def _get_credentials(self):
        creds = None
        script_dir = os.path.dirname(os.path.abspath(__file__))
        token_path = os.path.join(script_dir, "token.json")
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                credentials_path = os.path.join(script_dir, "credentials.json")
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, "w") as token:
                token.write(creds.to_json())
        return creds

    def _get_spreadsheet_id(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        spreadsheet_id_path = os.path.join(script_dir, "spreadsheet_id.txt")
        if os.path.exists(spreadsheet_id_path):
            with open(spreadsheet_id_path, "r") as f:
                spreadsheet_id = f.read().strip()
        else:
            # This part should ideally not be reached if the main app has already created it
            # But included for completeness
            spreadsheet = {
                'properties': {
                    'title': 'Budget App'
                }
            }
            spreadsheet = self.service.spreadsheets().create(body=spreadsheet,
                                                        fields='spreadsheetId').execute()
            spreadsheet_id = spreadsheet.get('spreadsheetId')
            with open(spreadsheet_id_path, "w") as f:
                f.write(spreadsheet_id)
            
            # Add header row to the main sheet (now named Transactions)
            header_values = [["Date", "Description", "Amount", "Type", "Category"]]
            self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id, range="Transactions!A1",
                valueInputOption="RAW", body={'values': header_values}).execute()

        # Ensure Budgets sheet exists
        spreadsheet_metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        sheets = [s.get('properties').get('title') for s in spreadsheet_metadata.get('sheets', '')]

        if "Budgets" not in sheets:
            body = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': "Budgets"
                        }
                    }
                }]
            }
            self.service.spreadsheets().batchUpdate(spreadsheetId=self.spreadsheet_id, body=body).execute()
            
            # Add header row to the Budgets sheet
            budget_header_values = [["Category", "Budget Limit"]]
            self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id, range="Budgets!A1",
                valueInputOption="RAW", body={'values': budget_header_values}).execute()

        return spreadsheet_id

    def add_transaction(self, date: str, description: str, amount: float, transaction_type: str, category: str = ""):
        try:
            # Validate date format
            datetime.strptime(date, "%Y-%m-%d")
            
            # Ensure amount is a float
            amount = float(amount)

            # Date (A), Description (B), Amount (C), Type (D), Category (E)
            values = [[date, description, amount, transaction_type, category]]
            body = {'values': values}
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id, range="Transactions!A:E",
                valueInputOption="USER_ENTERED", body=body).execute()
            
            return {"status": "success", "message": f"{result.get('updates').get('updatedCells')} cells updated. Transaction added."}
        except ValueError as ve:
            return {"status": "error", "message": f"Invalid input: {ve}. Please ensure date is YYYY-MM-DD and amount is a number."}
        except HttpError as err:
            return {"status": "error", "message": f"Google Sheets API error: {err}"}
        except Exception as e:
            return {"status": "error", "message": f"An unexpected error occurred: {e}"}
            
            # Assume appending to the bottom
#            row_index = len(self.get_all_transactions()["transactions"]) + 2  # +2 for header
            
#            return row_index

    def get_all_transactions(self):
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, range="Transactions!A:E").execute()
            values = result.get('values', [])
            
            transactions = []
            # Skip header row if present
            start_row = 0
            if values and values[0] == ['Date', 'Description', 'Amount', 'Type', 'Category']:
                start_row = 1

            for i, row in enumerate(values[start_row:]):
                sheet_row_index = i + start_row + 1 
                padded_row = row + ["" for _ in range(5 - len(row))]

                date = padded_row[0].strip()
                description = padded_row[1].strip()
                amount_str = padded_row[2].strip()
                transaction_type = padded_row[3].strip()
                category = padded_row[4].strip()

                try:
                    amount = float(amount_str)
                    transactions.append({
                        'date': date, 
                        'description': description, 
                        'amount': amount, 
                        'transaction_type': transaction_type, 
                        'category': category,
                        '_row_index': sheet_row_index
                    })
                except ValueError:
                    # Skip rows with invalid amounts
                    pass 
            return {"status": "success", "transactions": transactions}

        except HttpError as err:
            return {"status": "error", "message": f"Google Sheets API error: {err}"}
        except Exception as e:
            return {"status": "error", "message": f"An unexpected error occurred: {e}"}



    def find_matching_transactions(self, **criteria):
        all_txns_response = self.get_all_transactions()
        if all_txns_response["status"] != "success":
            return {"status": "error", "message": all_txns_response["message"]}

        transactions = all_txns_response["transactions"]

        def matches(txn):
            for key, value in criteria.items():
                if value is None:
                    continue
                txn_value = txn.get(key)
                if txn_value is None:
                    return False

                if key == "amount":
                    try:
                        if abs(float(txn_value) - float(value)) > 0.01:
                            return False
                    except:
                        return False
                else:
                    if str(txn_value).strip().lower() != str(value).strip().lower():
                        return False
            return True

        matches = [txn for txn in transactions if matches(txn)]

        return {"status": "success", "matches": matches}


    def _get_sheet_id_by_name(self, sheet_name):
        spreadsheet_metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        sheets = spreadsheet_metadata.get('sheets', '')
        for s in sheets:
            if s.get('properties').get('title') == sheet_name:
                return s.get('properties').get('sheetId')
        return None




    def edit_transaction(self, row_index=None, date=None, description=None, amount=None, transaction_type=None, category=None):
        # If row_index is provided, skip matching logic and go straight to delete + re-add
        if row_index is not None:
            print(f"[INFO] Editing by row_index: {row_index}")
            try:
                result = self.get_all_transactions()
                if result["status"] != "success":
                    # handle error, e.g.
                    return "Failed to retrieve transactions."

                transactions = result["transactions"]
                try:
                    original = transactions[row_index - 2]  # offset for header row
                except IndexError:
                    return f"Row index {row_index} is out of range."

            except IndexError:
                return f"Row index {row_index} is out of range."

            updated_transaction = {
                "date": date or original.get("date"),
                "description": description or original.get("description"),
                "amount": amount or original.get("amount"),
                "transaction_type": transaction_type or original.get("transaction_type"),
                "category": category or original.get("category"),
            }

            self.delete_transaction(row_index)
            self.add_transaction(**updated_transaction)
            return f"Transaction at row {row_index} updated by delete-and-recreate."

        # Fallback: find a matching transaction if row_index not provided
        criteria = {
            "date": date,
            "description": description,
            "amount": amount,
            "transaction_type": transaction_type,
            "category": category,
        }

        print(f"[DEBUG] edit_transaction called with criteria: {criteria}")
        result = self.get_all_transactions()
        if result["status"] != "success":
            raise Exception(result.get("message", "Failed to get transactions"))
        transactions = result["transactions"]


        def matches(txn, criteria):
            for key, value in criteria.items():
                if value is None:
                    continue
                txn_value = txn.get(key)
                if txn_value is None:
                    return False
                if key == "amount":
                    try:
                        if abs(float(txn_value) - float(value)) > 0.01:
                            return False
                    except:
                        return False
                elif key == "description":
                    if value.lower() not in txn_value.lower():
                        return False
                else:
                    if str(txn_value).strip().lower() != str(value).strip().lower():
                        return False
            return True

        for i, txn in enumerate(transactions):
            if matches(txn, criteria):
                row_index = i + 2
                print(f"[INFO] Found match at row {row_index}: {txn}")
                updated_transaction = {
                    "date": date or txn.get("date"),
                    "description": description or txn.get("description"),
                    "amount": amount or txn.get("amount"),
                    "transaction_type": transaction_type or txn.get("transaction_type"),
                    "category": category or txn.get("category"),
                }
                self.delete_transaction(row_index)
                self.add_transaction(**updated_transaction)
                return f"Transaction updated by delete-and-recreate at row {row_index}."

        print("[WARN] No matching transaction found.")
        return "No matching transaction found."




    # In budget_tools.py, inside BudgetSheetsManager:

#    def edit_transaction_by_recreate(self, date=None, description=None, amount=None, transaction_type=None, category=None):
#        # 1. Find matching transactions
#        find_result = self.find_matching_transactions(
#            date=date,
#            description=description,
#            amount=amount,
#            transaction_type=transaction_type,
#            category=category,
#        )
#        if find_result["status"] != "success":
#            return find_result
    
#        matches = find_result["matches"]
#        if len(matches) == 0:
#            return {"status": "error", "message": "No matching transaction found."}
#        elif len(matches) > 1:
#            return {"status": "ambiguous", "message": f"Multiple transactions found. Please be more specific."}

#        old_txn = matches[0]
#        row_index = old_txn["_row_index"]

        # 2. Delete the old transaction
#        delete_result = self.delete_transaction(row_index)
#        if delete_result["status"] != "success":
#            return delete_result

        # 3. Prepare new transaction data — use updated values or fallback to old if None
#        new_date = date or old_txn["date"]
#        new_description = description or old_txn["description"]
#        new_amount = amount if amount is not None else old_txn["amount"]
#        new_type = transaction_type or old_txn["transaction_type"]
#        new_category = category or old_txn["category"]

        # 4. Add new transaction
#        add_result = self.add_transaction(new_date, new_description, new_amount, new_type, new_category)
    
#        return add_result





    def get_all_existing_categories(self):
        categories = set()
        try:
            # Get categories from Budgets sheet column A
            budgets_result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, range="Budgets!A:A").execute()
            budgets_values = budgets_result.get('values', [])
            for row in budgets_values[1:]:  # skip header row
                if row and row[0]:
                    categories.add(row[0].strip())

            return {"status": "success", "categories": list(categories)}
        except HttpError as err:
            return {"status": "error", "message": f"Google Sheets API error: {err}"}
        except Exception as e:
            return {"status": "error", "message": f"An unexpected error occurred: {e}"}



    def delete_transaction(self, row_index: int):
        try:
            if row_index <= 1: # Prevent deleting header row
                return {"status": "error", "message": "Cannot delete header row or invalid row index."}

            requests = [{
                'deleteDimension': {
                    'range': {
                        'sheetId': self._get_sheet_id_by_name("Transactions"),
                        'dimension': 'ROWS',
                        'startIndex': row_index - 1, # Sheets API is 0-indexed for startIndex
                        'endIndex': row_index
                    }
                }
            }]
            self.service.spreadsheets().batchUpdate(spreadsheetId=self.spreadsheet_id, body={'requests': requests}).execute()
            
            return {"status": "success", "message": f"Transaction at row {row_index} deleted."}
        except HttpError as err:
            return {"status": "error", "message": f"Google Sheets API error: {err}"}
        except Exception as e:
            return {"status": "error", "message": f"An unexpected error occurred: {e}"}

    def modify_budget(self, category: str, budget_limit: float):
        try:
            # Fetch all budget limits to find the row index or if it's a new category
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, range="Budgets!A:B").execute()
            values = result.get('values', [])
            
            budget_row_index = -1
            # Skip header row if present
            start_row = 0
            if values and values[0] == ['Category', 'Budget Limit']:
                start_row = 1

            for i, row in enumerate(values[start_row:]):
                if len(row) >= 1 and row[0].strip().lower() == category.lower():
                    budget_row_index = i + start_row + 1 # 1-indexed row in sheet
                    break
            
            budget_limit = float(budget_limit) # Ensure limit is float

            if budget_row_index != -1:
                # Update existing budget
                update_range = f"Budgets!B{budget_row_index}"
                body = {'values': [[budget_limit]]}
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id, range=update_range,
                    valueInputOption="USER_ENTERED", body=body).execute()
                return {"status": "success", "message": f"Budget for {category} updated to {budget_limit:.2f}."}
            else:
                # Add new budget
                values = [[category, budget_limit]]
                body = {'values': values}
                self.service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id, range="Budgets!A:B",
                    valueInputOption="USER_ENTERED", body=body).execute()
                return {"status": "success", "message": f"Budget for {category} added with limit {budget_limit:.2f}."}

        except ValueError as ve:
            return {"status": "error", "message": f"Invalid input: {ve}. Please ensure budget limit is a number."}
        except HttpError as err:
            return {"status": "error", "message": f"Google Sheets API error: {err}"}
        except Exception as e:
            return {"status": "error", "message": f"An unexpected error occurred: {e}"}

# Example usage (for testing purposes, remove or guard in production)
if __name__ == "__main__":
    manager = BudgetSheetsManager()
    
    # Example: Add an income transaction
    # print(manager.add_transaction("2025-06-28", "Freelance Work", 500.00, "Income", "Work"))

    # Example: Add an expense transaction
    # print(manager.add_transaction("2025-06-28", "Groceries", 75.50, "Expense", "Food"))

    # Example: Get all transactions
    # transactions_response = manager.get_all_transactions()
    # if transactions_response["status"] == "success":
    #     for t in transactions_response["transactions"]:
    #         print(t)
    # else:
    #     print(transactions_response["message"])

    # Example: Edit a transaction (assuming row 2 is a valid transaction row)
    # print(manager.edit_transaction(2, description="Updated Groceries", amount=80.00))

    # Example: Delete a transaction (assuming row 3 is a valid transaction row)
    # print(manager.delete_transaction(3))

    # Example: Modify budget for a category
    # print(manager.modify_budget("Food", 300.00))
    # print(manager.modify_budget("Utilities", 150.00)) # Add new category
