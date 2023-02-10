# How To Use

This read me is split into several sections.

The first is a quick reference on specific environmental variables, and basic use
so people coming back to document can just look at that to remind themselves.

Second part is a quick start section, that has basic information on how to install
and use the config library in projects/code.

Third part goes in-depth on various topics, so someone looking for more details on how
config works can get them.

Table Of Contents:

- [How To Use](#how-to-use)
- [Special Environmental Variables](#special-environmental-variables)
    * [CONFIG_ENV_ONLY](#config_env_only)
    * [CONFIG_DISABLE_DEFAULT_CACHER](#config_disable_default_cacher)
    * [APP_ENV / SERVICE_NAME](#app_env--service_name)
- [Why Use](#why-use)
- [Quick Start / How To Install](#quick-start--how-to-install)
    * [Add via Poetry](#add-via-poetry)
    * [Using It](#using-it)
    * [Unit Tests](#unit-tests)
    * [Add Permissions](#add-permissions)
    * [Places Configuration is Retrieved From](#places-configuration-is-retrieved-from)
    * [Case Sensitivity](#case-sensitivity)
    * [Caching](#caching)
- [Overview](#overview)
    * [Historical Background](#historical-background)
    * [Summary](#summary)
    * [Service/Environment Names {#service-environment-names}](#serviceenvironment-names-%23service-environment-names)
        + [Search Order](#search-order)
    * [Quick Start](#quick-start)
    * [Naming Guidelines](#naming-guidelines)
    * [Standard Lookup Order](#standard-lookup-order)
    * [Standard Directory Paths](#standard-directory-paths)
    * [Exports](#exports)
- [Details / Reference](#details--reference)
    * [Configs are Cheap](#configs-are-cheap)
    * [Current Config](#current-config)
    * [Basics](#basics)
    * [Search Order](#search-order-1)
        + [Code Examples](#code-examples)
    * [Parent Chain](#parent-chain)
        + [How it's constructed](#how-its-constructed)
    * [Provider Chain](#provider-chain)
        + [Supported Providers](#supported-providers)
    * [Directory Chain](#directory-chain)
    * [Caching Details](#caching-details)
        + [Internal Local Memory Cacher](#internal-local-memory-cacher)
            - [Local Memory Caching Side Notes](#local-memory-caching-side-notes)
        + [DynamoCacher](#dynamocacher)
        + [Disable Default Dynamo Caching](#disable-default-dynamo-caching)
        + [Disable Cache + Non-Environmental Providers](#disable-cache--non-environmental-providers)
    * [Overrides](#overrides)
    * [Defaults](#defaults)
    * [Permissions](#permissions)


# Special Environmental Variables

Quick reference to commonly used things that you might need to lookup quickly and reference
while using config in an ongoing basis.

If you know nothing and want the basics, go to [Why Use](#why-use)


## CONFIG_ENV_ONLY

If 'true', by default Config will only use env-variables.

See [Disable Default Dynamo Caching](#disable-default-dynamo-caching)
See [Disable Cache + Non-Environmental Providers](#disable-cache-non-environmental-providers)


## CONFIG_DISABLE_DEFAULT_CACHER

If 'true', by default dynamo cacher will be disabled, unless specifically overridden.
(ie: the `Default` instance of the dynamo cacher is `None`).

See [Disable Default Dynamo Caching](#disable-default-dynamo-caching)


## APP_ENV / SERVICE_NAME

These are the defaults for `Config.service` and `Config.environment`,
that config uses to construct it's Default list of directories to search
when looking for things.

Also, these are used by DynamoCacher to determine the hash-key it uses to store cached values.
If either of these env-vars are blank/non-existant, then DynamoCacher will
fall-back to using `Config.service` and `Config.environment` for the hash-key it uses
for the DynamoCache table.


# Why Use

xyn-config's goal as a library is to simplify/abstract configuration lookup for our various
processors and services. Allows us to easily add new providers/services for configuration
with minimal changes to our projects (normally, just updating to latest `xyn-config` library).

It's also more secure to retrieve secrets at run time than store them as environmental
variables, since env-variables are normally stored in a task or lambda definition and are
more easily seen and usually not-encrypted (although that's improving over time in aws).


# Quick Start / How To Install

## Add via Poetry

`poetry add xyn-config`

You can simply add `xyn-config` via poetry as a dependency in your project.
The library is in Xyngular's gemfury repository, and should be installed from there.


## Using It

Now, you simply use it.  From the get-go, environmental variables will 'just work'.

Here are a few basic examples:

```python
from xyn_config import config

# If you had an environmental variable called `SOME_CONFIG_VARIABLE`, this would find it:
my_config_value = config.get('SOME_CONFIG_VARIABLE')

# Alternate Syntax:
# In this syntax, it's required that the first-char is upper-case:
my_config_value.SOME_CONFIG_VARIABLE
```

By default, Config will look at environmental variables first, and then other remote places second.

## Unit Tests

By default, unit tests will always start with a Config object that has caching disabled,
and only uses the environmental provider (ie: only looks at environmental variables).

This is accomplished via an autouse fixture in a pytest plugin module
(see plugin module `xyn_config.pytest_plugin` or fixture `xyn_config.pytest_plugin.xyn_config`).

If a project has `xyn-config` as a dependency, pytest will find this plugin module
and automatically use it. Nothing more to do.

As an FYI/side-note: There is a `xyn_resource.pytest_plugin.xyn_context` that will also
automatically  configure a blank context for each unit test.

This does mean you must configure Config using a fixture or at the top of your unit test method,
as any changes at the module-level will be forgotten.

The reason we do this is it guarantees that resources/config changes won't be propagaed/leak
into another unit test.

The end result is there is need to worry about these basics,
as they are taken care of for you automatically as long as the library is installed
as a dependency.


## Add Permissions

AWS services that we use for config values by default will restrict access to the values
by path/directory, and so you need to add permissions to the app to read these services/locations.

Repoman by default for serverless projects will add templated files to your project that will
create the needed permissions in aws when your project is deployed.

These permissions give access to remote locations/services where Xyngular currently stores
configuration information for our projects.

Here is a good example of the permissions you need to setup:

- [Hubspot's config permissions](https://github.com/xyngular/hubspot/blob/master/slsconfig/xynlib_config.yml)
- [Repoman template](https://github.com/xyngular/repoman/blob/master/src/templates/serverless/xynlib_config.yml)

For more details, see [Permissions](#permissions).


## Places Configuration is Retrieved From

By default, Config will look in these paths (first).
`SERVICE_NAME` and `APP_ENV` come from `config.APP_ENV` and `config.SERVICE_NAME`,
(which can be overridden if needed via config.service / config.environment):

- /{SERVICE_NAME}/{APP_ENV}/{VARIABLE_NAME}
- /{SERVICE_NAME}/{VARIABLE_NAME}
- /global/{APP_ENV}/{VARIABLE_NAME}
- /global/{VARIABLE_NAME}
- Details:
    - [Standard Directory Paths](#standard-directory-paths) 
    - [Directory Chain](#directory-chain)

For each directory/path, we go through these providers (second):

- Environmental Variables
- Dynamo Config Cache
- AWS Secrets Manager
- AWS Param Store
- Details:
    - [Provider Chain](#provider-chain)
    - [Supported Providers](#supported-providers)

In the order they are specified above (see [Standard Lookup Order](#standard-lookup-order)).

## Case Sensitivity

The directory/path is case-sensitive; but the `VARIABLE_NAME` part at the end is case-insensitive.

So environmental variables are entirely case-insensitive, as they only have the `VAIRABLE_NAME`
and no directory path.

So you can do `config.get('some_var_name')`, and it would still find a value for it,
even if the name in the source/provider of values is `SOME_VAR_NAME`.

## Caching

By default, values that are remotely looked up (ie: non-environmental variables)
are cached in a dynamo table.

When something is not in the cache table, Config will look at each configured provider
and when it finds the value (or lack of a value), it will store what it found in the
dynamo cache table for later faster lookup.

For details see [Caching Details](#caching-details), [Historical Background](#historical-background).

# Overview

xyn-config's goal as a library is to simplify/abstract configuration lookup for our various
processors and services.

## Historical Background

When we first started trying to get configuration from SSM dynamically,
we ran into a few issues.

We used a 3rd party library that helped us lookup vars based on paths in SSM.

It was slow because it looked up each config var separately, for each potential path.

We also got throttled by AWS. If you do to many calls to SSM you can be throttled,
and you get back an error instead of the configuration value.

We also wanted to more easily work with other services in the future,
in a way that did not tie them to the codebase. The idea is we can switch and/or use
additional services in the future and the rest of the codebase does not have to change.

We decided back then to write up a Config class to solve all these issues.
We were able to speed up the queries to the services, and cache things to help prevent throttling,
and cache the results in dynamo to make it even faster and more resilient against throttling.

## Summary

We have a few basic/general concepts in xyn-config that you should be familiar with
when working with the library.

Below is a sort of summary / outline of the basic general concepts, with links
to more details.

The top level of the below list is the concepts, with some basic info as sub-list items,
followed by a link to more details.


- Providers
    - There are a number of providers, and we expect to add more as needed over time.
    - Each represents a service and/or place that xyn-config can retrieve config values/info from.
        - Each one can provider some or all of the configuration information that is needed.
    - example of providers include, but are not limited to:
        - Environmental variables
        - AWS Secrets Manager
        - AWS SSM param store
    - For details see:
        - [Provider Chain](#provider-chain)
        - [Supported Providers](#supported-providers)
- Directories
    - Basically, paths used with providers to lookup configuration information in.
    - example: '/myService/prod/'
    - Each path is used with each provider, to ask provider for config values at a specific path.
    - Some providers ignore directory paths, such as the environmental variable provider.
    - In the service the provider is connecting to, the directory could have any number of keys 
    (config variable name) along with the key's associated value.
    - For more info see (Standard Directory Paths)(#standard-directory-paths)
    - For details see [Directory Chain](#directory-chain)
- Grabbing Values
    - Simply ask a config object for a value via upper-case attribute:
    - `config.CLIENT_ID`
    - Or use `get` method `xyn_config.config.Config.get`.
    - get method lets you pass in a default value, just like `dict.get`.
- Current Config / Resources
    - There is a concept that there is a 'current/active' default config object that can be used
    at any time.
    - This is accomplished via xyn-resource library (see `xyn-resource`).
    - You can get the current config object via `Config.resource()`.
    - There is a convenient proxy config object you can use that represents the current Config object.
    - The proxy can be used as if it's the current config object.
    - Below you see us importing the config proxy and then using it to get a value:
    - `from xyn_config import config`
    - `config.get('some_config_var_name')`
    - For details see [Current Config](#current-config)
- Parents
    - When you activate a new Config object, the current one is its parent.
    - With the activated one being the 'current' and the old one being a parent.
    - You can use `with` to activate a Config object.
    - Here is how you might temporarily change the providers to use by default:
        - `with Config(providers=[...]):`
    - Each Config object knows about their parent.
    - Parent is consulted when resolving defaults/overrides.
    - There is an app-root Config object that is shared between threads.
    - You can turn off this parent-lookup behavior if needed, but by default it's on.
    - If desired, you can create a Config object and pass it around instead of using the 'current'.
        - It's usually more convenient to just use the current/default config.
    - For details see [Parent Chain](#parent-chain).
- Overrides
    - Some overrides can happen as part of `xyn_config.config.Config.__init__`.
    - Such as `service`, `environment`, `providers`, etc.
    - You can also change them after Config object is created via attributes.
    - For normal configuration values, you can override thoese as well.
    - `config.CLIENT_ID = 'override-client-id-value`
    - Parent config objects are consulted when checking for overrides.
    - If there is an overrided, first one found is what it used.
    - For details see [Overrides](#overrides).
- Caching
    - Dynamo is used to temporarily cache discovered configuration values.
    - Table's name is `global-configCache`.
    - This makes startup of things like lambdas on average faster, as most of the time the cache will
    tell them everything they need in one request.
    - Prevents throttling as we don't have to ask SSM for values as often.
    - This was one of the original motivating factors for creating the library.
    - Also, lets you see what configuration values are currently resolved for a service.
    - Developer and simply look in the table, see what values are being resolved.
    - For details see [Caching](#caching)


## Service/Environment Names {#service-environment-names}

There are two special variables that `xyn_config.config.Config` treats special:

1. `Config.SERVICE_NAME`
    - Normally comes from an environmental variable `SERVICE_NAME`.
    - This is typically the name of the app.
    - We normally `camelCase` these (see [Naming Rules][naming-guidelines] for details).
2. `Config.APP_ENV`
    - Normally comes from an environmental variable `APP_ENV`.
    - This is the name of the environment.
    - Standard environments:
          - prod
          - testing
          - dev
    - An individual developer can use their name, such as `joshOrr`.
    - We normally `camelCase` these (see [Naming Rules][naming-guidelines] for details).


.. warning:: New projects should set these two ^ variables to an appropriate value
    either via environmental variable or by setting it directly on the main/current `config`
    at the very start of the app's
    launch before doing anything else to ensure it's known/used while importing/using other code.

.. important:: For these two ^ special values, `Config` skips the normal [Provider Chain][provider-chain].

### Search Order

Config will only look in these locations for the special variables
`Config.SERVICE_NAME` and `Config.APP_ENV`:

1. First, [Overrides] (including and any overrides in the [Parent Chain][parent-chain]).
2. Environmental variables next (directly via `os.getenv`, NOT the provider).
    - **This is how most projects normally do it.**
    - Even if the `xyn_config.providers.environmental.EnvironmentalProvider` is **NOT** in the
      [Provider Chain][provider-chain] we will still look for `SERVICE_NAME`/`APP_ENV` in the
      environmental variables (all other config values would not).
3. [Defaults] last (including any defaults in the [Parent Chain][parent-chain]).

## Quick Start
[quick-start]: #quick-start

Let's start with a very simple example:

```python
# Import the default config object, which is an 'alias' to the
# currently active config object.
from xyn_config import config

# Get a value from the currently active config object, this special
# config object will always lookup the currently active config object
# and let you use it as if it was the real object.
value = config.SOME_CONFIG_VALUE
```

This will look up the current `xyn_config.config.Config` class and ask it for the
`SOME_CONFIG_VALUE` value. It will either give you the value or a None if it does not exist.

The general idea is: The underlying 'app/service' setup will provide the properly setup 
ready-to-use `xyn_config.config.Config` as a resource (`xyn_resource.resource.Resource`).
So you can just import this special `xyn_config.config.config` variable to easily always
use current `xyn_config.config.Config.current` resource.

## Naming Guidelines

- `Config.SERVICE_NAME` and `Config.APP_ENV` values should be named with no spaces but using
  `camelCase` to separate any words.
- Alternatively, you can also use under-scores (`_`) as word separators; but the preference 
  is `camelCase`.
- We use the `-` to separate names from other names in a single string for services that can't
  use `/` in a resource name (such as Dynamo table names). So definitely **don't** use `-` inside
  the `SERVICE_NAME`.
- In order to get/set a config value via `config.SOME_NAME`, the first character must be an upper-case
  letter. If you need to look up a config value that starts with some other character, use
  `Config.get` or `Config.set_override`.
- Config names are case **insensitive** 
    - example: If we want the SERVICE_NAME, you could get the
      value via `config.SERVICE_NAME` or `config.Service_Name`, it would return the same value).
    - By convention, we always upper case
      them in code and generally lower-case them in the various aws providers.
- Directory paths are case **sensitive** (see [Directory Paths][standard-directory-paths]);
  like this: `/myCoolService/joshOrrEnv/...`.
    - The service name and env name that make up the `xyn_config.directory.Directory.path`
      is case-sensitive. But the part after that for the config name is **NOT**.

## Standard Lookup Order

By Default, Config will look at the following locations by default
(see [Provider Chain][provider-chain] for details):

1. Config [Overrides](#overrides)
2. Environmental Variables
    - via `xyn_config.providers.environmental.EnvironmentalProvider`.
3. Dynamo flat config cache, Details:
    - [Info About Caching][caching]
    - via `xyn_config.providers.dynamo.DynamoCacher`
4. AWS Secrets Provider via `xyn_config.providers.secrets_manager.SecretsManagerProvider`.
5. AWS SSM Param Store via `xyn_config.providers.ssm_param_store.SsmParamStoreProvider`.
6. Config [Defaults](#defaults)

## Standard Directory Paths
[standard-directory-paths]: #standard-directory-paths

Most of the providers have a 'path' you can use with them. I call the path up until just
before the config variable name a directory (see `xyn_config.directory.Directory`).

If no `Config.SERVICE_NAME` has been provided or is set to `None`
(either from a lack of an environmental variable `SERVICE_NAME`, or via
[override](#overrides) or [default](#defaults)) then we can't use paths that need this value.

At that point, the `Default` Directories searched are these
(see [Directory Chain][directory-chain]; changeable via `Config.directories`):

1. `/global/{APP_ENV}`
2. `/global`

If there is a `Config.SERVICE_NAME` value available, then we will add two extra directories by
`Default` to the [Directory Chain][directory-chain]:

1. `/{SERVICE_NAME}/{APP_ENV}`
2. `/{SERVICE_NAME}/`
3. `/global/{APP_ENV}`
4. `/global/`

If the `Config.APP_ENV` is not configured, it defaults to `dev` at the moment.

As soon as something provides the `APP_ENV` and/or `SERVICE_NAME` to the config by setting
it directly as an override or as a default (or if something changes the app environmental 
variables directly, I dislike doing that for a number of reasons though) it will start 
immediately using the full directory paths, ie: `/{service_name}/{app_env}`, etc.

The `Config` class is more dynamic... you can think of it as more of a 'view' or 'lens', so
[Configs Are Cheap][configs-are-cheap].

So this "view" and/or "lens" can now be easily changed.  You can do an override like this:

```python
from xyn_config import config
config.SERVICE_NAME = "someServiceName"
```

Or set a default (if it can't find the value anywhere else):

```python
from xyn_config import config
config.set_default("service_name", "someServiceName")
```

By default, [overrides] and [defaults] are inherited from the [Parent Chain][parent-chain].

## Exports

.. note:: This is something we have not really utilized yet
   (Config supports it, but we don't really use this feature anywhere currently).

Services/Apps can export values to other apps/services. The standard location for them are:

- `/{OtherApp's-->SERVICE_NAME}/export/{APP_ENV}`

You can add them via `Config.add_export` to let a config object search that export path
last (after all other normal directory paths).


# Details / Reference

Provides the basic `Config` class, which is used to provide a basic interface to get config values.

## Configs are Cheap
[configs-are-cheap]: #configs-are-cheap

Before we continue, I want to emphasize something. `Config` is more of a "view" or a "lens" then
something that directly keeps configuration values.  There are a number of resources that
Config uses to get configuration values behind the scenes that the Config objects share.
Because of this Config objects are cheap to create and throw away.

So if you want to change some aspect of Config's
configuration, without effecting the rest of the app by changing the main/default/current
config you can always allocate a Config object anytime you want and just throw it away whenever
you want.

Here is a code example that creates a `Config` object where the first directory
checked is `/some/dir_path` followed by whatever the Default would normally
be. I then askes it for `SOME_NAME`. It's prefectly fine to do this, the Config object will
still be very fast, as the resources it uses behind the scenes stay allocated and will already
have the value for `SOME_NAME` if it's been asked for previously.

```python
from xyn_config import Config
from xyn_types import Default
def my_function_is_called_a_lot():
    my_config = Config(directories=[f"/some/dir_path", Default])
    the_value_I_want = my_config.SOME_NAME
```

## Current Config

The Config class is a xyn-resource, `xyn_resource.resource.Resource`;
meaning that there is a concept that there is a 'current' or 'default' Config object
that can always be used.

You can get it your self easily anywhere asking `Config` for it's `.resource()`.

```python
# Import Config class
from xyn_config import Config

# Ask Config class for the current one.
config = Config.resource()
```

Most of the time, it's more convenient to use a special ActiveResourceProxy object that you can
import and use directly. You can use it as if it's the current config object:

```python
from xyn_config import config

# Use it as if it's the current/default config object,
# it will proxy what you ask it to the real object
# and return the result:
config.get('SOME_CONFIG_NAME')
```

## Basics

We have a list of `xyn_config.provider.Provider` that we query, in a priority order.
We also have a list of `xyn_config.directory.Directory` in priority order as well
(see [Provider Chain][provider-chain] and [Directory Chain][directory-chain]).

For each directory, we ask each provider for
that directories value for a particular config-var name.

You can allocate a new `Config`() object at any time, and by default [unless you pass
other options into the __init__], it will used a set of shared resources from the
current context. Due to this, creating a Config object is normally very quick.
Especially since the config object will lazily setup most of the internal resources
on demand when it's needed [ie: someone asks for a config var of some sort]. If a previous
Config object was created in the past, most of these resources will already be setup
and be fast to retrieve.

You can use `Config` as if the config-var is directly on the object:
```python
from xyn_config import Config
value = Config().SOME_VAR
```

There is also a `DefaultConfig` object that's pre-created and always available at
`config`. You can use it just like a normal Config object; every time
it's used it will lookup the current config object and direct the retrieval to it.

Here is an example:
```python
from xyn_config import config
value = config.SOME_VAR
```

This is equivalent of doing `Config.current().SOME_VAR`. You can call any method
you want on config that Config supports as well:
```python
from xyn_config import config
value = config.get("SOME_VAR", "some default value")
```

## Search Order
[search-order]: #search-order

Here is the order we check things in when retrieving a value:

1. [Overrides](#overrides) - Value is set directly on `Config` or one of Config's parent(s).
    - For more details about parents, see [Parent Chain][parent-chain].
2. `xyn_config.providers.environmental.EnvironmentalProvider` first if that provider is
   configured to be used. We don't cache  things from the envirometnal provider, so it's always
   consutled before the cache. See topic [Provider Chain][provider-chain] or the
   `xyn_config.provider.ProviderChain` class for more details.
3. High-Level flattened cache if it was not disabled (see [Caching][caching]).
4. All other [Providers][provider-chain] / [Directories](#directory-chain)
     - Looked up based first on [Directory Order][directory-chain]
     - Second by [Provider Order][provider-chain].
     - That is, we go though each provider for the first directory; if value still not found
       we go though each provider using the second directory, and so on.
5. [Defaults][defaults] - Finally, if value still has not been found we look at the defaults
    provided to `Config` or Config's parent (see [Parent Chain][parent-chain]).

### Code Examples

Basic, average/normal example:
```python
from xyn_config import config

assert config.APP_ENV == "testing"

# provider order is:
#    DynamoProvider
#    SsmProvider

# directories to search are:
#    "/global/testing"
#    "/global"

# values:
#    ssm has: "/global/testing/SOME_NAME" = "SSM-V-1"
#    dynamo has: "/global/SOME_NAME" = "Dynamo-V-1"

assert config.SOME_NAME == "SSM-V-1"

# If we instead have:
#    ssm has: "/global/testing/SOME_NAME" = "SSM-V-1"
#    dynamo has: "/global/SOME_NAME" = "Dynamo-V-1"
#    dynamo has: "/global/testing/SOME_NAME" = "Dynamo-V-2"

assert config.SOME_NAME == "Dynamo-V-2"
```


Here is an example of setting and using an override:
```python
from xyn_config import config

# if we have values:
config.SOME_NAME = "some parent value"

# We get this:
assert config.SOME_NAME == "some parent value"

# If instead we have these values:
config.SOME_OTHER_NAME = "parent-other-value"

with Config():
    # And this:
    config.SOME_NAME = "child-value"

    # We would get this:
    assert config.SOME_OTHER_NAME == "parent-other-value"
    assert config.SOME_NAME == "child-value"

# Since the child-context is no longer the current one, we revert back to previous:
assert config.SOME_NAME == "some parent value"
```

Example of using defaults.

I am using a more complex example here, to illustrate how parents and defaults work:

```python
from xyn_config import Config, config

# If we have these defaults in the 'parent' config:
config.set_default(f"SOME_OTHER_NAME", "parent-default-value")
config.set_default(f"ANOTHER_NAME","parent-default-another-v")

# Create a new child Config objects with different defaults:
with Config(defaults={
    f'SOME_OTHER_NAME': 'default-other-value',
    f'SOME_NAME': 'default-value'
}):
    assert config.APP_ENV == "testing"

    # provider-chain has this in order:
    #    DynamoProvider
    #    SsmProvider

    # directory-chain contains this in order:
    #    "/global/testing"
    #    "/global"

    # values:
    #    ssm has: "/global/testing/SOME_NAME" = "SSM-V-1"
    #    dynamo has: "/global/SOME_NAME" = "Dynamo-V-1"

    assert config.SOME_OTHER_NAME == "default-other-value"
    assert config.SOME_NAME == "SSM-V-1"
    assert config.ANOTHER_NAME == "parent-default-another-v"
```

Here is an example of modifying the current config to add a directory in it's current
[Directory Chain][directory-chain].

```python
from xyn_config import Config
from xyn_config.directory import Directory

# Even if this function is called a lot, what we do with
# config should still be fast enough.
def my_function_is_called_a_lot():
    my_config = Config()
    my_config.add_directory(Directory(service=f"a_service", env=f"myDevEnv"))
    my_config.add_directory(f"/some/other/path")
    the_value_I_want = my_config.SOME_NAME
```


## Parent Chain
[parent-chain]: #parent-chain
There is a concept of a parent-chain with Config.
When a new Config object is activated as the new current/default Config object,
the one that was previously the current Config object will now become the first parent.

A parent can have a parent.  Eventually there will be a 'root' parent that has no parent.
This will normally be the config object that was first created the application first started.

Unless another Config object has been activated since the application started,
the current config object may be the root-config object, and therefore have no parent.

The parent chain is generally consulted when:

- We are getting the list of providers, directories, getting the cacher, and so on; and we encounter
  a `xyn_types.default.Default` value while doing this.We then consult the next parent in the
  To Resole this `Default` value, Config consults the current parent-chain.
  If when reaching the last parent in the chain, we still have a `Default` value,
  sensible/default values are constructed and used.
- While getting a configuration value `Config` will look for [Overrides][overrides]
  and [Defaults][defaults] in `self` first, and then the parent chain second.

### How it's constructed

If the Config object has their `use_parent == True` (it defaults to True) then it will allow
the parent-chain to grow past it's self in the past/previously activated Config objects.

Config is a xyn-resource Resource.  Resource uses a `xyn_resource.context.Context` object to
keep track of current and past resources.

The parent-chain starts with the current config resource (the one in the current Context).
If that context has a parent context, we next grab the Config resource from
that parent context and check it's `Config.use_parent`. If `True` we keep doing
this until we reach a Config object without a parent or a `Config.use_parent` 
that is False.

If the `Config.use_parent` is `False` on the Config object that is currently being asked for a
config value:

- If it does not find it's self in the parent-chain (via Context) then the parent-chain
  will be empty at that moment.  This means it will only consult its self and no other Config object.
  The idea here is the Config object is not a resource in the
  `xyn_resource.context.Context.parent_chain`
  and so is by its self (ie: alone) and should be isolated in this case.
- If it finds its self, it will allow the parent-chain to grow to the point it finds its
  self in the Context parent-chain. The purpose of this behavior is  to allow all the 'child'
  config objects to be in the parent-chain. If one of these children has the use_parent=False,
  it will stop at that point and **NOT** have any more child config objects included in the
  parent-chain.
  
  As long as the object is still in the context-hierarchy above that child that had
  use_parent=False it will contain the child objects.


We take out of the chain any config object that is myself. The only objects in
the chain are other Config object instances.

Each config object is consulted until we get an answer that is not a `xyn_types.Default`;
once that is found that is what is used.

Example: If we had two Config object, `A` and `B`. And when `B` was originally constructed,
directory was left at it's `xyn_types.Default` value.

And `A` is the parent of `B` at the time `B` was asked for its directory_chain
(ie: `xyn_config.config.Config.directory_chain`). This would cause `B` to ask `A` for their
directory_chain because `A` is in `B`'s parent-chain. The directory_chain from `A` is what `B`
would use for it's list of `xyn_config.directory.Directory`'s to look through when resolving
a configuration value (see `Config.get`).

Here is an example:

```python
from xyn_config import Config

# This is the current config
A = Config.current()

# We make a new Config, and we DON'T make it 'current'.
# This means it's not tied to or inside any Context [like `A` above is].
B = Config()

assert B.directory_chain == A.directory_chain

# Import the special config object that always 'acts' like the current config
# which in this case should be `A`.
from xyn_config import config
assert B.directory_chain == config.directory_chain
```

See [Directory Chain][directory-chain] (later) for what a
`xyn_config.directory.DirectoryChain` is.

## Provider Chain
[provider-chain]: #provider-chain

`Config` uses an abstract base class `xyn_config.provider.Provider` to allow for various
configuration providers. You can see these providers under the `xyn_config.providers` module.

Each `Config` class has an ordered list of these providers in the form of a
`xyn_config.provider.ProviderChain`. This chain is queried when looking for a config value.
Once a value is found, it will be cached by default [if not disabled] via a
`xyn_config.providers.dynamo.DynamoCacher`.

The dynamo cacher will cache values that are
looked up externally, such as by `xyn_config.providers.ssm_param_store.SsmParamStoreProvider`,
for example. If we use a provider such as `xyn_config.providers.environmental.EnvironmentalProvider`,
since this found it locally in a process environmental variable it does not cache it.

The providers are queried in the order they are defined in the `Config.provider_chain`.
If you provide a set of providers as part of creating a `Config.__init__`, the provider_chain
will be in the order the user provided in the \__init__ method.

By `Default`, the `Config.provider_chain` is inherited from the [Parent Chain][parent-chain].

### Supported Providers
    
- `xyn_config.providers.environmental.EnvironmentalProvider`
- `xyn_config.providers.dynamo.DynamoProvider`
- `xyn_config.providers.dynamo.DynamoCacher`
- `xyn_config.providers.ssm_param_store.SsmParamStoreProvider`
- `xyn_config.providers.secrets_manager.SecretsManagerProvider`

.. todo:: Need to document how to setup permissions in a serverless project to provide correct
    access to the specific providers for ssm/dynamo/etc.
    For now, look at [Permissions](#permissions) section for real-works examples of what is needed.

## Directory Chain
[directory-chain]: #directory-chain

Some providers have a path/directory concept, where they have various different sets of config
name/values at a specific path. The path is what we call a specific
`xyn_config.directory.Directory`. We can get the list of directories that will be queried
via `Config.directory_chain`. It returns a `xyn_config.directory.DirectoryChain` that has
a list of directories in a specific order.  We search a specific directory on all of our providers
before searching the next directory.

By `Default`, the `Config.directory_chain` is inherited from the [Parent Chain][parent-chain].

For a list of `Default` directories we normally use, and how they would by used to lookup
see [Standard Directory Paths](#standard-directory-paths).

## Caching Details

There are two types of caching in py-xyn-config:

- Caching in internal/local memory.
    - Providers use the InternalLocalProviderCache to accomplish this.
    - InternalLocalProviderCache cache key is per-provider instance.
      So if a new provider is allocated and made active, it will start out with a blank cache.
      (the older provider still has access to its cache).
- Caching in a special Dynamo cache table.
    - After checking environmental provider (if enabled), normally the DynamoCache table
      is the next provider that is consulted.  If it has the value, then Config will use that.
      If it does not, then the other providers are consulted (such as the SSM provider).
      When the value is determined, it will be cached in the DynamoCache table.
    - The DynamoCache table stores a flattened list of all config values, so once we determine
      a value for something and store it in DynamoCache, it's very fast to ask for and retrieve
      that value again in the future (even in other instance of a lambda since it's a dynamo table).
    - The DynamoCacher provider still uses the InternalLocalProviderCache to store a local copy of
      the remote/retrieved dynamo table cached values so that it does not have to keep looking
      up individual values every time it's asked for them.

### Internal Local Memory Cacher

The `xyn_config.provider.InternalLocalProviderCache` is a resource that is centrally used
by the other providers (including the DynamoCacher provider) to store what values they have
retrieved from their service locally, in a sort of local-memory-cache.

It's important to locally cache the values for at least some amount of time because the providers
bulk-retrieve values at a particular directory level in bulk (ie: one request to retrieve as many
values in a particular directory path/location as possible).
They do this for optimization purposes, it massively speeds up future lookups of configuration
values since they are already retrieved, and we don't have to make more round-trip requests.

The cache is centralized so management of when to expire the cache is all in one place,
and so that the cache for all providers expire simultaneously. This is important,
and the class doc as more details of why.

Eventually this internal memory provider cache will expire its cache of values.
The default is currently 15 minutes from when the first thing is cached locally.

You can change the amount of time via two ways:

- When an instance of `InternalLocalProviderCache` is created, it will look for the environmental
  variable named `CONFIG_INTERNAL_CACHE_EXPIRATION_MINUTES`. If it exists and is true-like
  it's converted into an `int` and then used as the number of minutes before the cache expires.
- Modifying `xyn_config.provider.InternalLocalProviderCache.expire_time_delta`.
  You can easily modify it by getting the current resource instance and changing the attribute.
  (via `InternalLocalProviderCache.resource().expire_time_delta`)
      - `expire_time_delta` is a `datetime.timedelta` object. You can use whatever time-units
        you want by allocating a new `timedelta` object.
            - Example: `timedelta(minutes=5, seconds=10)`, for 5 minutes and 10 seconds.

If environmental variable is not set and nothing changes the `expire_time_delta` directly,
it defaults to 15 minutes.

You can always reset the entire cache by calling this method on the current resource instance:
`xyn_config.provider.InternalLocalProviderCache.reset_cache`.

#### Local Memory Caching Side Notes

There is also an option on `xyn_config.config.Config.get` that allows you to ignore the local
memory cache (as a convenience option).

Right now it does this by resetting the entire cache for you before lookup.
But in the future, it may be more precise about what it does and may just retrieve that specific
value from each provider until it finds
(vs resetting the cache and bulk retrieving everything all over again).
Mostly depends on how often we would really need to do this in the future.
I am guessing it would be rare so the current implementation should be good enough for now.

### DynamoCacher

The cache is meant to provide a fast-way to lookup configuration values, and is the main way
in which fast/scaled-executing processes such as Lambda's will probably get their values.

The cache has a built-in TTL (time-to-live) after which it will be deleted from the cache.
In addition, the `xyn_config.providers.dynamo.DynamoCacher` generates a random number and
subtracts that from the TTL when querying for values. That way it may see things as not in
the cache sooner then it normally would without that. The purpose behind this is to not flood
SSM or other configuration services with a bunch of requests at the same time when the cache
for a number of values are suddenly expired.  This random expiration reduces the chance of
that happening by isolating the config lookup and cache refresh to hopefully only one Lambda
instance, (for example) and not all of them at the same time.

When a CONFIG name/value pair is not in the cache, the we lookup them up in the provider chain,
get the value and put it into the cache if it's a cacheable value [ie: not an environmental
variable].

The cache is a flattened list of all of the configuration values for a specific set of
`xyn_config.providers` and `xyn_config.directory.Directory`'s.

Because the order of the Directories and Providers determine which values we find and ultimately
cache... the cache's Dynamo hash key is made up of:
 
 - `Config.APP_ENV`
 - `Config.SERVICE_NAME`
 
 And the range key is made up of:
 
 -  Config value name as lower-case (example: `xynapi_base_url`).
 - Each provider name in `Config.provider_chain`, seprated by `|-|`
 - `Config.directory_chain`
 
AWS permissions are by the dynamo hash key, and that controls what the app can get/set in the cache.

The dynamo range key is additional unique information. The combination of all of it determins an
individual cache-key value that can be set/retrieved from the cache.  We do this so that
if code changes the configuration [directories/providers] on a config object the
results from the cache will still be accurate.

.. todo:: Need to document how to setup permissions in a serverless project to provide correct
    access to the specific cache hash-key for the app. For thoese intrested, look at the
    serverless.yml file in the hubspot repo.

### Disable Default Dynamo Caching

First, let's talk about how to disable caching via environmental variables:

- `CONFIG_DISABLE_DEFAULT_CACHER`, if 'true':
    - Only by default will the cache will be disabled.
    - This only happens while resolving the `Default` on `xyn_config.config.Config.cacher`.
    - If you set `DynamoCacher` directly on `xyn_config.config.Config.cacher` via code,
    caching will still be used regardless.
    - Using this option disables the cacher without having to also disable the providers,
    this means it will still lookup params from SSM and so on, just not use the cached version.
- `CONFIG_ENV_ONLY`, if 'true':
    - Regardless of how Config is modified/configured via code, these effects will still happen:
        - The cache will be disabled.
        - The only provider that will be used is the EnvironmentalProvider.
    - See [Disable Cache + Non-Environmental Providers](#disable-cache-non-environmental-providers)



While developing, it's sometimes nice to always grab the values each time you run something
and to NOT cache it. But you only want to do this while running it locally,
you don't want to modify the code it's self to disable caching.

You can set an environmental variable called `CONFIG_DISABLE_DEFAULT_CACHER` to `True` if you
want to easily disable caching by default.

..important:: The code will use `xyn_config.providers.environmental.EnvironmentalProvider` for this.
    So if you change this environmental variable WHILE in the middle of running the code
    `xyn_config.providers.environmental.EnvironmentalProvider` via debugger or other means,
    provider may have already taken its snapshot of the environmental variables and Config
    won't see the change.
    
    You could of course do a `with EnvironmentalProvider():` to force
    using a new provider instance and therefore, it will take a new snapshot.
    But it's far easier to just do `config.cacher=None` while in debugger/code when you want
    to dynamically disable the cacher.

We don't check overrides/Config for this; only settable via an environmental variable.
This is so you don't have to modify the code to disable cacher by Default,
and so only accessible via environmental variable.

BUT if someone passes `Config(cacher=DynamoCacher)` explicitly we will use that
regardless of what `CONFIG_DISABLE_DEFAULT_CACHER` is set too.
The `CONFIG_DISABLE_DEFAULT_CACHER` will only disable it if `cacher=Default`
(which it does by default).

If you want to permanently disable cacher via code, do the following instead:

{There is an autouse fixture that will disable the cacher during unit tests,
as an example real-world use-case in xyn-config's pytest_plugin module: `xyn_config.pytest_plugin.xyn_config`}

```python
from xyn_config import Config, config

# Globally/Permanently:
config.cacher = None

# Temporarily via `with`:
from xyn_config import Config
with Config(cacher=None):
    pass

# Temporarily via decorator:
from xyn_config import Config
@Config(cacher=None)
def some_method():
    pass
```

### Disable Cache + Non-Environmental Providers

If you set `CONFIG_ENV_ONLY` as an actual environmental variable, it will disable
all providers and the cache too.  It needs to be in `os.environ`, so a real environmental variable.

- CONFIG_ENV_ONLY: If 'true', by default Config will only use env-variables.
    - If something has specifically set providers, the won't be used while CONFIG_ENV_ONLY is on.
    - Cache is also explicitly disabled when CONFIG_ENV_ONLY is on, no mater how Config is setup.
  
As a developer, it's nice sometimes to just 'disable' Config, where it only looks at
environmental variables (along any normal overrides/defaults set into it, as it normally would).

The objective with this CONFIG_ENV_ONLY is to disable external lookup of any configuration
variables.  Only rely on what is inside the code/process.

This can help with debugging, to see if a problem is due to a coding issue or if it's
some sort of configuration issue.

Or if there is a special process being run that should only use environmental variables.


## Overrides

You can override a value on a `Config` object in two ways:

1. `Config.set_override`
2. Setting it directly as an attribute, ie:
2. Setting it directly as an attribute, ie:
```
from xyn_config import config
config.SOME_CONFIG_NAME = "some config value"
```

The use cases for this feature can include (but are not limited to):

1. Unit-tests, you can override values per-test.
2. CLI programs. Any command-line options can be set as overrides into the current config object.
   This will 'override' the config values with the CLI options provided by user.
3. When you need to setup a specific environment for a special process (such as producing docs).

When you override a config name/value, it will always be returned regardless of any configured
providers or caching that would normally happen. The value also won't be cached. The override
is meant only for that config object and any child-config objects.

This means any child Config object will also see and use this value, overriding any value it
may normally have returned. This works internally by looking at the [Parent Chain][parent-chain].
The first parent found to have an override for a config name
will be the value used. If us or no parent has it overridden, the Config object will lookup
the value via the providers/cacher like normal (see [Fundamentals][fundamentals]).

If you only want to temporarily override a value, you can do something like this:
```
from xyn_config import config

# Activate a new Config object instance:
with Config():
    # Rhe override will only be on the current Config object,
    # which was the one created in `with` above. 
    config.OVERRIDE_NAME = "some temporarily overridden value"
    
    # Execute code here that needs this value.
    assert config.OVERRIDE_NAME == "some temporarily overridden value"

# <-- At this point, the Config object we created above would no longer be
#     the active/default one; whatever it was before `with` above is what
#     it will be now.
assert config.OVERRIDE_NAME is None

# Override via a decorator; remember: var-names are case-insensative
@Config(defaults={'override_name': 'default-value'})
def some_method():
    # Execute code that needs this value.
    assert config.OVERRIDE_NAME == "default-value"

# We execute method, it will have a temporary Config object, but it will be
# thrown away after method is done executing.
some_method()
assert config.OVERRIDE_NAME is None
```

When unit-testing: There are some pytest plugin autouse fixtures that will automatically
create a good, blank baseline for Config.  For details see [Unit Tests](#unit-tests)

## Defaults
[defaults]: #defaults

You can take a look at `Config.set_default` for more info. In a nut-shell, if some value can't
be found anywhere else and there is a default set for it, we return the default.  The defaults
will be inherited from the parent if not first found on child. You can override a default on a
child config object by simply setting the default on the child.

> :warning: todo: Put an example in here about how it goes though each directory/provider when finding
    a value.

> :warning: todo: Move this into xyn_config, I think this overview would be better suited there
    since it talks about the other sub-modules, like providers, cacher, etc.

> :warning: todo: Document/implement new cache key scheme where the RANGE key has the
    provider chain + directory chain in it.

## Permissions

Repoman by default for serverless projects will add templated files to your project that will
create the needed permissions in aws when your project is deployed.

These permissions give access to the various places where Xyngular currently stores
configuration information for our projects (for more details, keep reading).

Each source/provider of configuration info has their own permission needs.
Such as AWS param store, or AWS secrets manager.

Here is a good example of the permissions you need to setup:

- [Hubspot's config permissions](https://github.com/xyngular/hubspot/blob/master/slsconfig/xynlib_config.yml)
- [Repoman template](https://github.com/xyngular/repoman/blob/master/src/templates/serverless/xynlib_config.yml)

By default, if Config gets a permission denied error from a source of configuration,
it will log this but then continue on.

So it should be generally safe to only configure permissions for the path(s) you actually need.
Config will get what it can and use that.

> :warning: Warning: Config will only log a single warning for each unique permission error.
    If an app does not have permission to a particular directory path on one of the
    provider services in aws; Config will catch that error and log a **warning** the first
    time it encounters that error.  Subsequently, it will remember for that provider + directory
    combination that it had an error and not attempt it again. This is to preserve the performance
    of the system so that it does not get bogged down constantly trying to query inaccessible
    locations. I've tried to limit it to only permission errors and letting other types of
    errors to propagate back to the app [via Exceptions] like you would normally expect.

