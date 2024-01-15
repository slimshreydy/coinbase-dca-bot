# Modal Skeleton

Skeleton for simple repos that deploy functions to [Modal](modal.com).

## Workflow

1. Make a virtualenv and then run `make setup`.
2. Set up Github secrets in repo for Modal API keys. Use the envvar names `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET`.
3. Edit `main.py` with application logic.
4. Add any new requirements for the Modal container in `requirements.txt`
5. Push changes to main. The changes will autodeploy to Modal on push.