# Test data

`reference/` holds a small, fixed set of made-up stores, suppliers, products, product aliases,
committee members and vehicles. The tests use these files instead of your real
`data/reference/` files, so their expected answers don't change when you edit your own
reference data.

`google_form_export.csv` is a real download of the Google Form's responses (#28), with one test
check sent from a phone. It keeps the export's quirks on purpose: the time is in GMT+3, and some
question titles have their description on a second line, or a space in front.

If you change a file here, some tests will expect different answers.
