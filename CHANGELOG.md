# Changelog

## [0.3.3](https://github.com/xyngular/py-xcon/compare/v0.3.2...v0.3.3) (2023-02-21)


### Bug Fixes

* move dev-only dependencies to correct group. ([0830fec](https://github.com/xyngular/py-xcon/commit/0830fece38c3964a772b3cd93a5d02c21a5565a7))

## [0.3.2](https://github.com/xyngular/py-xcon/compare/v0.3.1...v0.3.2) (2023-02-20)


### Bug Fixes

* doc-generator for pdoc3 dependencies. ([f8ca9f1](https://github.com/xyngular/py-xcon/commit/f8ca9f133c3610fe507c4d7959e67be73450e57b))

## [0.3.1](https://github.com/xyngular/py-xcon/compare/v0.3.0...v0.3.1) (2023-02-20)


### Bug Fixes

* project publishing metadata ([d4a2886](https://github.com/xyngular/py-xcon/commit/d4a2886ee1a2ef3a88db58fd6c4d9f83538b700a))
* reame file name case. ([dd9e513](https://github.com/xyngular/py-xcon/commit/dd9e5137d4e80e3c94dc45dee0035b4ff7dd5898))
* remove xyn_config refs (now it's `xcon`). ([223666f](https://github.com/xyngular/py-xcon/commit/223666f9085ede6a008b967dfac77ff50a5d685f))

## 0.3.0 (2023-02-20)


### Features

* ability to use format-style paths with Directory objects. ([5d44735](https://github.com/xyngular/py-xcon/commit/5d44735a83beb9ba20c3550d59f9f715d98144fa))
* ability to use formatted directory paths, changeable default directory paths. ([1816e63](https://github.com/xyngular/py-xcon/commit/1816e639ab009e5ebaeafb02af90bf76ceb95bca))
* add a bunch of documentation, rename things to fit `xcon` name better. ([6120fd7](https://github.com/xyngular/py-xcon/commit/6120fd73b2add437c120fac14d1f6c64128523b7))
* added serverless yml files that can be copied or directly used to support config-cache (if wanted/needed) ([f3c154d](https://github.com/xyngular/py-xcon/commit/f3c154dda5e79b54313034bf5b46464b726ea1de))
* by default use `all` for all environments, instead of nothing. ([9cb5593](https://github.com/xyngular/py-xcon/commit/9cb55939a5f4b0c20e779d7c7cf99fc9e941275e))
* have pdoc3 document the other dependent modules. ([c821d7b](https://github.com/xyngular/py-xcon/commit/c821d7bb62963e77bd4c3741867d8e61ccdfc2ae))
* initial code import, using `xcon` for library name. ([79ec325](https://github.com/xyngular/py-xcon/commit/79ec32526e0f6e28c5eb3f03b368d36e5f84f026))
* rename dynamo cache/provider tables hash-key/range-key to be more self-descriptive. ([f3707fc](https://github.com/xyngular/py-xcon/commit/f3707fc0d8a97f1be8af1e4b45bf264e3058dc10))
* renamed/reconfigured dependcies, got unit tests working. ([ad325ad](https://github.com/xyngular/py-xcon/commit/ad325adb81826f8a5de2a45d3eeda1b2a4045e2b))
* use xcon.conf.Settings.[environment/service] instead of SERVICE_NAME on Config object; etc. ([54709ba](https://github.com/xyngular/py-xcon/commit/54709babb4cf4de5d117e5624ff7201ff8f55a7d))


### Bug Fixes

* add tomlkit dep ([3db114e](https://github.com/xyngular/py-xcon/commit/3db114e1deeb1bd354d44274451cc82d6394e830))
* remove unneeded code ([f08e057](https://github.com/xyngular/py-xcon/commit/f08e05726678d3cb1f3dbf160f19a44f0631b4d6))
* type in name. ([d8df718](https://github.com/xyngular/py-xcon/commit/d8df718aa1579b863c051ccdfa189548415013f3))


### Documentation

* fix doc url ref. ([7be339b](https://github.com/xyngular/py-xcon/commit/7be339b449d0a71273e75525a610f8c99f926af2))
* helps doc-generator to not make these inherit from ABC ([8857908](https://github.com/xyngular/py-xcon/commit/8857908750b60f9232ef9d943dd56bd8fc0fc6b4))
* one last note about the current state of things. ([55c3dd4](https://github.com/xyngular/py-xcon/commit/55c3dd4308f6e69fdb28500ceef68475ae39372c))
