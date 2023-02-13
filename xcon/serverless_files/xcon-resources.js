module.exports = async ({ options, resolveVariable }) => {
    const execSync = require('child_process').execSync;

    // import { execSync } from 'child_process';  // replace ^ if using ES modules

    // the default is 'buffer'
    // Assumes project is using `poetry` to manage dependencies + python virutal environment.
    let command = 'poetry run -q python -c "import os; from xcon import serverless_files; print(f\'{os.path.dirname(serverless_files.__file__)}\', end=\'\');"'
    let output = execSync(command, { encoding: 'utf-8' });

    // Use can simply do this to include a resource file:
    // (copy xcon-resource.js into project):

    // # *** file: serverless.yml ***
    //
    // custom:
    //   xconResourcePath: ${file(./xcon-resources.js)}
    //
    // resources:
    //   - ${file(${self:custom.xconResourcePath}/cache-permissions.yml)}

    return `${output}`
}
