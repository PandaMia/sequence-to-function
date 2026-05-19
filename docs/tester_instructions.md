# Tester Instructions

## Goal

Verify that the Sequence-to-Function service responds correctly through the UI, can search gene-related data, uses the database, formats responses properly, and handles clarification questions.

## Link

Open the application: https://stf.pandamia.org/

## What to Test

### 1. Basic Availability

- Open the application in a browser.
- Check that the chat UI loads.
- Check that the input field is available and that a message can be sent.

### 2. Simple Database Query

Send:

```text
show me 5 genes
```

Expected result:

- the service returns a list of genes;
- the response is displayed as normally formatted text, not as JSON or a table;
- the text does not overflow outside the response block.

### 3. Search by Specific Gene

Send:

```text
show information about DAF-16
```

Expected result:

- the agent searches data by `gene`;
- if records exist in the database, the agent uses them;
- the response contains a structured description related to function, aging, or longevity if such data is available.

### 4. Search by UniProt ID

Send:

```text
show information about protein_uniprot_id O16850
```

Expected result:

- the agent searches data by `protein_uniprot_id`;
- the result is connected to the corresponding gene;
- the response should not say that search is only possible by gene name.

### 5. Clarification Question and Buttons

Send an ambiguous request:

```text
show me genes
```

Expected result:

- if the agent asks a clarification question, the answer options should be displayed as clickable buttons;
- clicking a button should send the selected option to the agent;
- buttons should not appear in regular final responses with results.

### 6. Markdown Formatting

Send:

```text
give me a short markdown report about DAF-16
```

Expected result:

- headings, lists, emphasis, and code values are rendered as markdown;
- the user sees only the formatted response, without a separate `message_format` column or field.

### 7. Request with Web/Literature Search

Send:

```text
find recent literature about DAF-16 and longevity and prepare a short report
```

Expected result:

- the agent can use literature search;
- already known articles should not be parsed again if they exist in the database;
- new relevant sources may be added to the database;
- the final response should be a clear report, not a tool log.

### 8. UI Robustness Check

Send a long request, for example:

```text
prepare a detailed report about DAF-16 including function, longevity association, known evidence, and available article references
```

Expected result:

- the long response stays inside the response block;
- scrolling is available if needed;
- lines, links, and code fragments do not break the layout.
