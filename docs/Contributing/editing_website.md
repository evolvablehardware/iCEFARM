# Editing This Website

This website is created with Material for MkDocs and is deployed with github actions.

[Material for MkDocs Website](https://squidfunk.github.io/mkdocs-material/reference/){.md-button .md-button--primary}

## Editing

To see the website as you are working on it, you need to run `mkdocs serve`.

First, install all dependancies. These are described near the end of the `.github\workflows\deploy_website.yml` file, and look like this:

``` bash
pip install mkdocs-material mkdocs-redirects mkdocs-minify-plugin mkdocs-git-revision-date-localized-plugin mkdocs-awesome-nav
```

Next, run the following command in a terminal:

``` bash
mkdocs serve
```

This should build the website and update it as you make changes. If the website does not automatically launch, look for a message like:

    INFO    -  [##:##:##] Serving on http://127.0.0.1:8000/

Then, you should put that address into a webbrowser to see the webpage.

## Publishing

The webpage is automatically built and released onto Github via Github Actions. All you need to go is `git commit` and `git push`, then it should show up on the main page.