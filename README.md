# Coinbase DCA Bot

Coinbase currently lets you do recurring investments so you can perform [dollar cost averaging](https://www.investopedia.com/terms/d/dollarcostaveraging.asp),
but only on their casual trader fee tier. This means DCAing small amounts of money (e.g. $10) could incur fees of up to 10%.
This bot submits daily orders on the Coinbase Advanced Trading product for you so you can DCA with fees of < 0.60%.

## How to Use

1. Make an account on [Modal.com](https://modal.com/).
2. Get an API token for Coinbase from [Coinbase Cloud](https://cloud.coinbase.com/access/api). Make sure to select `Trading token`.
3. Under the [Secrets tab in Modal](https://modal.com/slimshreydy/secrets), add a new secret namespace called `coinbase` and add two new secrets called `COINBASE_KEY_NAME` and `COINBASE_PRIVATE_KEY`.
4. Run `make setup` to set up the repo locally.
5. Specify your preferred DCA policy in `config.json`. See below for more info on config format.
6. Run `make push-policy` to sync your new policy to Modal.
7. Run `make deploy` to deploy your cronjob. You can also push to `main` to accomplish this.

## Config Format

`config.json` is generated by running `make setup` locally. `config.template.json` is a sample config you can reference.

The format expected for `config.json` is:

```
{
    "policies": [
        {
            "token": "<asset code, e.g. BTC>",
            "budget": <how much to buy in one purchase, in USD. should be at least $10 to stay above the minimum buy.>,
            "frequency": <number of days in between buys. higher number means fewer buys. minimum of 1.>
        }
    ],
    "boosts": [  // optional, see more below
        {
            "multiplier": <number to multiply your investments by for a short time>,
            "end_date": "<ISO 8601 timestamp of when to stop boosting investments, e.g. 2024-01-01T00:00:00Z>"
        }
    ]
  ]
}
```

## Tips and details

- Coinbase Advanced Trading has a [maker-taker fee structure](https://help.coinbase.com/en/coinbase/trading-and-funding/advanced-trade/advanced-trade-fees). This means you can get a slightly cheaper fee by placing orders that don't fulfill instantaneously (i.e. they don't match sell orders already on the books). This bot optimizes this for you by ever so slightly undercutting the current ask price by 0.05%. Since crypto prices fluctuate aggressively, this means most times you'll benefit from lower maker fees while still getting your order filled quickly. However, occasionally your order won't go through if the token keeps mooning.
- Many tokens have a minimum buy on Coinbase, so **stick to minimum budgets of $10** to avoid errors.
- The bot executes at 3pm EST every day. If you don't want to purchase a given token every day, you can set the `frequency` for that token > 1. For example, a frequency of `2` means to buy every 2 days.
- If you want to DCA into a token for < $10/day, just set a $10 `budget` with `frequency` > 1. This means you'll spend $10 every few days, which works out to a smaller daily effective budget.
- Sometimes if the market is high volatile, you may be interested in temporarily boosting the amount you invest daily (e.g. doubling your amount invested for 1 week). You can do this by specifying a boost in `config.json`. Generally you just need to specify what factor you want to boost by, and when to stop boosting.
- If you'd like to temporarily stop DCA'ing, you can also use the `boosts` feature to stop investing by just setting a multiplier of 0.
