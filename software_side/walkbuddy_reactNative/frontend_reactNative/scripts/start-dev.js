const {
  spawn,
  spawnSync,
} = require('child_process');

const fs = require('fs');
const https = require('https');
const path = require('path');


/*
  ==================================================
  PATHS
  ==================================================
*/

const PROJECT_DIRECTORY =
  path.resolve(
    __dirname,
    '..'
  );

const SERVER_DIRECTORY =
  path.join(
    PROJECT_DIRECTORY,
    'agora_session_server'
  );

const HELPER_DIRECTORY =
  path.join(
    PROJECT_DIRECTORY,
    'helper_web'
  );

const TOOLS_DIRECTORY =
  path.join(
    PROJECT_DIRECTORY,
    '.tools'
  );

const LOCAL_CLOUDFLARED =
  path.join(
    TOOLS_DIRECTORY,
    process.platform === 'win32'
      ? 'cloudflared.exe'
      : 'cloudflared'
  );

/*
  ==================================================
  CONFIG
  ==================================================
*/

const BACKEND_PORT = 3001;
const HELPER_PORT = 3002;

const processes = [];


/*
  ==================================================
  UTILITIES
  ==================================================
*/

function sleep(ms) {
  return new Promise(
    resolve =>
      setTimeout(resolve, ms)
  );
}


function commandExists(command) {
  const checker =
    process.platform === 'win32'
      ? 'where'
      : 'which';

  const result =
    spawnSync(
      checker,
      [command],
      {
        stdio: 'ignore',
        shell: true,
      }
    );

  return result.status === 0;
}


function startProcess(
  name,
  command,
  args,
  options = {}
) {
  console.log(
    `\n[STARTING] ${name}`
  );

  const child =
    spawn(
      command,
      args,
      {
        shell: true,
        ...options,
      }
    );

  processes.push(child);

  child.on(
    'exit',
    code => {
      console.log(
        `[${name}] exited with code ${code}`
      );
    }
  );

  return child;
}


/*
  ==================================================
  SESSION SERVER
  ==================================================
*/

function startSessionServer() {
  return startProcess(
    'Session Server',

    'node',

    ['server.js'],

    {
      cwd:
        SERVER_DIRECTORY,

      stdio:
        'inherit',
    }
  );
}


/*
  ==================================================
  HELPER WEB SERVER
  ==================================================
*/

function startHelperServer() {
  return startProcess(
    'Helper Web Server',

    'npx',

    [
      'serve',
      '.',
      '-l',
      String(HELPER_PORT),
    ],

    {
      cwd:
        HELPER_DIRECTORY,

      stdio:
        'inherit',
    }
  );
}


/*
  ==================================================
  CLOUDFLARED DOWNLOAD URL
  ==================================================
*/

function getCloudflaredDownloadUrl() {
  const platform =
    process.platform;

  const arch =
    process.arch;


  if (
    platform === 'win32' &&
    arch === 'x64'
  ) {
    return (
      'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe'
    );
  }


  if (
    platform === 'win32' &&
    arch === 'arm64'
  ) {
    return (
      'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-arm64.exe'
    );
  }


  if (
    platform === 'linux' &&
    arch === 'x64'
  ) {
    return (
      'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64'
    );
  }


  if (
    platform === 'linux' &&
    arch === 'arm64'
  ) {
    return (
      'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64'
    );
  }


  throw new Error(
    `Automatic cloudflared download is not configured for ${platform}/${arch}`
  );
}


/*
  ==================================================
  DOWNLOAD FILE
  ==================================================
*/

function downloadFile(
  url,
  destination
) {
  return new Promise(
    (resolve, reject) => {

      const request =
        https.get(
          url,
          response => {

            if (
              response.statusCode >= 300 &&
              response.statusCode < 400 &&
              response.headers.location
            ) {
              response.resume();

              return downloadFile(
                response.headers.location,
                destination
              )
                .then(resolve)
                .catch(reject);
            }


            if (
              response.statusCode !== 200
            ) {
              response.resume();

              reject(
                new Error(
                  `Download failed with HTTP ${response.statusCode}`
                )
              );

              return;
            }


            const file =
              fs.createWriteStream(
                destination
              );


            response.pipe(file);


            file.on(
              'finish',
              () => {
                file.close(
                  () =>
                    resolve()
                );
              }
            );


            file.on(
              'error',
              error => {

                try {
                  fs.unlinkSync(
                    destination
                  );
                } catch {
                  // Ignore cleanup failure.
                }

                reject(error);
              }
            );

          }
        );


      request.on(
        'error',
        reject
      );

    }
  );
}


/*
  ==================================================
  ENSURE CLOUDFLARED
  ==================================================
*/

async function ensureCloudflared() {

  /*
    First check global install.
  */

  if (
    commandExists(
      'cloudflared'
    )
  ) {
    console.log(
      '✓ cloudflared detected globally'
    );

    return 'cloudflared';
  }


  /*
    Then project-local cached copy.
  */

  if (
    fs.existsSync(
      LOCAL_CLOUDFLARED
    )
  ) {
    console.log(
      '✓ Using cached local cloudflared'
    );

    return LOCAL_CLOUDFLARED;
  }


  /*
    Otherwise download automatically.
  */

  console.log(
    'cloudflared not found.'
  );

  console.log(
    'Downloading cloudflared automatically...'
  );


  fs.mkdirSync(
    TOOLS_DIRECTORY,
    {
      recursive: true,
    }
  );


  await downloadFile(
    getCloudflaredDownloadUrl(),
    LOCAL_CLOUDFLARED
  );


  if (
    process.platform !==
    'win32'
  ) {
    fs.chmodSync(
      LOCAL_CLOUDFLARED,
      0o755
    );
  }


  console.log(
    '✓ cloudflared downloaded'
  );


  return LOCAL_CLOUDFLARED;
}


/*
  ==================================================
  CLOUDFLARE QUICK TUNNEL
  ==================================================
*/

function startCloudflareTunnel(
  name,
  cloudflaredCommand,
  port
) {
  return new Promise(
    (resolve, reject) => {

      console.log(
        `\n[STARTING] ${name}`
      );

      console.log(
        `Target: http://localhost:${port}`
      );


      const child =
        spawn(
          cloudflaredCommand,

          [
            'tunnel',
            '--url',
            `http://localhost:${port}`,
          ],

          {
            shell: true,

            stdio: [
              'ignore',
              'pipe',
              'pipe',
            ],
          }
        );


      processes.push(child);


      let resolved =
        false;


      const handleOutput =
        data => {

          const text =
            data.toString();


          process.stdout.write(
            text
          );


          const match =
            text.match(
              /https:\/\/[a-zA-Z0-9.-]+\.trycloudflare\.com/
            );


          if (
            match &&
            !resolved
          ) {
            resolved = true;


            console.log(
              `\n✓ ${name} ready`
            );


            resolve({
              provider:
                'cloudflare',

              url:
                match[0],

              process:
                child,
            });
          }
        };


      child.stdout.on(
        'data',
        handleOutput
      );


      child.stderr.on(
        'data',
        handleOutput
      );


      child.on(
        'error',
        error => {

          if (!resolved) {
            reject(error);
          }
        }
      );


      child.on(
        'exit',
        code => {

          if (!resolved) {
            reject(
              new Error(
                `${name} exited before creating a tunnel. Exit code ${code}`
              )
            );
          }
        }
      );


      setTimeout(
        () => {

          if (!resolved) {
            reject(
              new Error(
                `Timed out waiting for ${name}`
              )
            );
          }

        },
        45000
      );

    }
  );
}


/*
  ==================================================
  EXPO
  ==================================================
*/

function startExpo(
  backendUrl,
  helperUrl
) {
  console.log(
    '\n========================================'
  );

  console.log(
    ' STARTING EXPO'
  );

  console.log(
    '========================================'
  );

  console.log(
    `Backend URL: ${backendUrl}`
  );

  console.log(
    `Helper URL:  ${helperUrl}`
  );

  console.log(
    '========================================\n'
  );


  startProcess(
    'Expo',

    'npx',

    [
      'expo',
      'start',
      '--dev-client',
      '--clear',
    ],

    {
      cwd:
        PROJECT_DIRECTORY,

      stdio:
        'inherit',

      env: {
        ...process.env,

        EXPO_PUBLIC_AGORA_SESSION_URL:
          backendUrl,

        EXPO_PUBLIC_HELPER_PAGE_URL:
          helperUrl,
      },
    }
  );
}


/*
  ==================================================
  CLEANUP
  ==================================================
*/

function shutdown() {

  console.log(
    '\nStopping development services...'
  );


  for (
    const child of
    processes
  ) {
    try {
      child.kill();
    } catch {
      // Ignore cleanup failure.
    }
  }


  process.exit();
}


process.on(
  'SIGINT',
  shutdown
);


process.on(
  'SIGTERM',
  shutdown
);


/*
  ==================================================
  MAIN
  ==================================================
*/

async function main() {

  console.log(
    '\n========================================'
  );

  console.log(
    ' WalkBuddy Cloudflare Development'
  );

  console.log(
    '========================================'
  );

  /*
    STEP 1:
    Make sure cloudflared exists.
  */

  const cloudflared =
    await ensureCloudflared();


  /*
    STEP 2:
    Start both local services.
  */

  startSessionServer();

  startHelperServer();


  await sleep(
    2000
  );


  /*
    STEP 3:
    Backend tunnel.
  */

  const backendTunnel =
    await startCloudflareTunnel(
      'Backend Cloudflare Tunnel',

      cloudflared,

      BACKEND_PORT
    );


  /*
    STEP 4:
    Helper tunnel.
  */

  const helperTunnel =
    await startCloudflareTunnel(
      'Helper Cloudflare Tunnel',

      cloudflared,

      HELPER_PORT
    );


  /*
    STEP 5:
    Show final URLs.
  */

  console.log(
    '\n========================================'
  );

  console.log(
    ' DEVELOPMENT ENVIRONMENT READY'
  );

  console.log(
    '========================================'
  );

  console.log(
    'Backend provider: Cloudflare'
  );

  console.log(
    `Backend URL:      ${backendTunnel.url}`
  );

  console.log('');

  console.log(
    'Helper provider:  Cloudflare'
  );

  console.log(
    `Helper URL:       ${helperTunnel.url}`
  );

  console.log(
    '========================================\n'
  );


  /*
    STEP 6:
    Start Expo.
  */

  startExpo(
    backendTunnel.url,
    helperTunnel.url
  );
}


main().catch(
  error => {

    console.error(
      '\nSTARTUP FAILED:'
    );

    console.error(
      error
    );


    shutdown();

  }
);