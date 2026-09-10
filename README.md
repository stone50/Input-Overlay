# Usage

- To permit reading kernel inputs when not running as `root`, run `sudo usermod -aG input $USER`

- In the same directory as the executable, add a `config.json` file:
```
{
    "API_PORT": <port number>
}
```

- In OBS, create a browser source with the URL set to `http://127.0.0.1:<port number>`, and the size set to 1079x269.

- Now when you run this project, OBS should display the overlay. It may be required to refresh or deactivate+reactivate the browser source depending on your setup.
