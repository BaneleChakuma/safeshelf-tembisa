# Shelf checks from a phone: the Google Form (#28)

Committee members can record a shelf check on their phone with a Google Form, instead of filling
in a CSV file. The Form has the same fields as the shelf-check template
([`data/templates/README.md`](../data/templates/README.md)). Its responses are downloaded as a CSV
file and imported into `data/incoming/`, then the pipeline validates and loads them like any other
file.

## 1. Make the Form

Go to [forms.google.com](https://forms.google.com), start a blank form and call it
**SafeShelf shelf check**. Add these questions **in this order, with exactly these titles**: the
importer finds each answer by its question's title.

| # | Question title | Type | Required | Options and settings |
|---|---|---|---|---|
| 1 | `Store` | Dropdown | Yes | One option per store, ID first: `ST01 Amandla Superette`, `ST02 Ikhaya Spaza`, `ST03 Thokoza Foods`, `ST04 Ubuntu Mini Market`, `ST05 Siyakhula Groceries`, `ST06 Lethabo Spaza`, `ST07 Masakhane Cash Store`, `ST08 Kasi Corner Shop`, `ST09 Phumelela Supermarket`, `ST10 Ithemba Food Store` |
| 2 | `Product` | Dropdown | Yes | `White Bread 700g`, `Brown Bread 700g`, `Fresh Milk 1L`, `Fresh Milk 2L`, `Amasi 2L`, `Maize Meal 5kg`, `Maize Meal 10kg`, `Large Eggs 6 Pack`, `Large Eggs 18 Pack`, `Cola 2L`, `Orange Juice 1L`, `Cooking Oil 2L`, `Sugar 2.5kg`, `Rice 2kg`, `Polony 1kg`, `Potato Chips 125g`, `Hot Cross Buns 6 Pack`, `Yoghurt 1kg` |
| 3 | `Batch number` | Short answer | Yes | Description: "The batch number printed on the packaging" |
| 4 | `Expiry date` | Date | Yes | Description: "The expiry or best-before date on the packaging" |
| 5 | `How many are on the shelf?` | Short answer | Yes | Response validation: **Number**, **Greater than**, `0` |
| 6 | `Condition` | Multiple choice | Yes | `OK`, `Expired`, `Mouldy`, `Damaged packaging`, `Swollen`, `Not cold` |
| 7 | `Your committee member ID` | Short answer | Yes | Description: "For example CM01. Never your name." Response validation: **Regular expression**, **Matches**, `CM\d+` |
| 8 | `Photo file name (optional)` | Short answer | No | Description: "The name of the photo on your phone, for example IMG_0042.jpg" |

You don't need a question for when the check was done: Google adds a **Timestamp** to every
response, and SafeShelf uses it as the time of the check.

The store and product options come from `data/reference/stores.csv` and
`data/reference/products.csv`. When a store or product is added there, add it to the Form too.

## 2. Settings that matter (POPIA)

- **Settings → Responses → Collect email addresses: Do not collect.** Committee members are
  recorded by their ID only, never by name or email. If the Form does collect them, the importer
  leaves them out and warns you, but it's better not to collect them at all.
- **Settings → Responses → Allow response editing: off**, so a check can't be changed after it's sent.
- Share the Form's link only with committee members.

## 3. Publish it and send the link to committee members

A Form doesn't take responses until it's published. Press **Publish** at the top right. If it asks
who can respond, choose **Anyone with the link**, and confirm. Then press the **🔗** icon next to
it and copy the responder link. Share it with committee members, for example on WhatsApp. On a
phone, the Form opens in the browser, and adding it to the home screen makes it one tap away.

Before sharing it, open the Form's **Preview** (the 👁 icon) and check that `0` in "How many are on
the shelf?" and a name in "Your committee member ID" are both refused.

The name of the downloaded file comes from the Form's name in Google Drive, at the very top left
("Untitled form" until you change it), not from the title inside the Form.

## 4. Import the responses

1. In the Form, open **Responses**, press the **⋮** next to the responses (not the one at the top
   of the page) and choose **Download responses (.csv)**. Google downloads a zip file, such as
   `SafeShelf shelf check.csv.zip`. There's no need to unzip it.
2. Import it:

   ```bash
   PYTHONPATH=src python -m safeshelf import-form ~/Downloads/"SafeShelf shelf check.csv.zip"
   ```

   It writes the new responses to `data/incoming/shelf_checks_<today>_form.csv` and says how many
   there were.
3. Load them with the rest: `PYTHONPATH=src python -m safeshelf run`.

You can download and import as often as you like. The download always has every response, so the
importer skips the ones it imported before, and writes the new ones to a new file
(`_form2`, `_form3` ... for a second or third import on the same day).

A response that breaks a rule, such as an unknown member ID, goes to `data/rejected/` with the
reason, like any other row.

If the import says a question is missing, check that the Form's question titles match the table
above. Capitals and spelling must match. Spaces around a title don't matter, and neither does text
on a second line of the title (if a description was typed into the title by mistake), but it's
neater to put descriptions in the description box (**⋮ → Description**).

**Times.** Google writes each response's time in the time zone of the Google account that owns the
Form, for example `2026/10/26 4:41:47 PM GMT+3`. The import turns every time into South African
time (GMT+2), so that one is recorded as 15:41.

**Dates.** The Form's own download writes the Expiry date year first, like `2026-10-24`, which
SafeShelf reads correctly (checked with a real download). If you ever export from a linked Google
Sheet instead, set the Sheet's locale to **South Africa** first (**File → Settings → Locale**), so
dates aren't written month first.
