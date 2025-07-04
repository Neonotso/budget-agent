from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def get_access_token(token_file="token.json"):
    creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise Exception("Credentials are invalid and cannot be refreshed.")
    return creds.token

if __name__ == "__main__":
    token = get_access_token()
    print("Access Token:", token)
