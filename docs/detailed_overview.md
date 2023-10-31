---
title: Detailed Overview
---

???+ warning "Docs not finished and are out of date!"
    This Detailed Overview document is particular out of date, and needs a lot of updating.
    Please take what's in here with a grain of salt, so to speak.
    It will be fixed up soon.

    This is pre-release software, based on another code base and the docs
    have not yet been completely finished/changed to accommodate the changes
    made to clean aspects of it.

    For now, if you see refrences/names to things that don't exist
    or have slightly different names in code, just beware of the situation.

    Thank you for your support while the code base transitions to being open-source!


# Overview

xcon's goal as a library is to simplify/abstract configuration lookup for our various
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

We have a few basic/general concepts in xcon that you should be familiar with
when working with the library.

Below is a sort of summary / outline of the basic general concepts, with links
to more details.

The top level of the below list is the concepts, with some basic info as sub-list items,
followed by a link to more details.


- Providers
    - There are a number of providers, and we expect to add more as needed over time.
    - Each represents a service and/or place that xcon can retrieve config values/info from.
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
    - Or use `get` method `xcon.config.Config.get`.
    - get method lets you pass in a default value, just like `dict.get`.
- Current Config / Resources
    - There is a concept that there is a 'current/active' default config object that can be used
    at any time.
    - This is accomplished via xinject library (see `xinject`).
    - You can get the current config object via `Config.grab()`.
    - There is a convenient proxy config object you can use that represents the current Config object.
    - The proxy can be used as if it's the current config object.
    - Below you see us importing the config proxy and then using it to get a value:
    - `from xcon import config`
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
    - Some overrides can happen as part of `xcon.config.Config.__init__`.
    - Such as `service`, `environment`, `providers`, etc.
    - You can also change them after Config object is created via attributes.
    - For normal configuration values, you can override thoese as well.
    - `config.CLIENT_ID = 'override-client-id-value`
    - Parent config objects are consulted when checking for overrides.
    - If there is an overrided, first one found is what it used.
    - For details see [Overrides](#overrides).
- Caching
    - Dynamo is used to temporarily cache discovered configuration values.
    - Table's name is `global-all-configCache`.
    - This makes startup of things like lambdas on average faster, as most of the time the cache will
    tell them everything they need in one request.
    - Prevents throttling as we don't have to ask SSM for values as often.
    - This was one of the original motivating factors for creating the library.
    - Also, lets you see what configuration values are currently resolved for a service.
    - Developer and simply look in the table, see what values are being resolved.
    - For details see [Caching](#caching)


## Service/Environment Names {#service-environment-names}

There are two special variables that `xcon.config.Config` treats special:

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


???+ warning "New projects should set these two ^ variables to an appropriate value"
    either via environmental variable or by setting it directly on the main/current `config`
    at the very start of the app's
    launch before doing anything else to ensure it's known/used while importing/using other code.

???+ important "For these two ^ special values, [`Config`](../api/xcon/config.html#xcon.config.Config){target=_blank} skips the normal [Provider Chain][provider-chain]."

### Search Order

Config will only look in these locations for the special variables
`Config.SERVICE_NAME` and `Config.APP_ENV`:

1. First, [Overrides] (including and any overrides in the [Parent Chain][parent-chain]).
2. Environmental variables next (directly via `os.getenv`, NOT the provider).
    - **This is how most projects normally do it.**
    - Even if the [`xcon.providers.environmental.EnvironmentalProvider`](../api/xcon/providers/environmental.html#xcon.providers.environmental.EnvironmentalProvider){target=_blank} is **NOT** in the
      [Provider Chain][provider-chain] we will still look for `SERVICE_NAME`/`APP_ENV` in the
      environmental variables (all other config values would not).
3. [Defaults] last (including any defaults in the [Parent Chain][parent-chain]).

## Quick Examples
[quick-start]: #quick-start

Let's start with a very simple example:

```python
# Import the default config object, which is an 'alias' to the
# currently active config object.
from xcon import config

# Get a value from the currently active config object, this special
# config object will always lookup the currently active config object
# and let you use it as if it was the real object.
value = config.SOME_CONFIG_VALUE
```

This will look up the current `xcon.config.Config` class and ask it for the
`SOME_CONFIG_VALUE` value. It will either give you the value or a None if it does not exist.

The general idea is: The underlying 'app/service' setup will provide the properly setup 
ready-to-use `xcon.config.Config` as a resource (`xinject.dependency.Dependency`).
So you can just import this special `xcon.config.config` variable to easily always
use current `xcon.config.Config.current` resource.

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
    - The service name and env name that make up the `xcon.directory.Directory.path`
      is case-sensitive. But the part after that for the config name is **NOT**.

## Standard Lookup Order

By Default, Config will look at the following locations by default
(see [Provider Chain][provider-chain] for details):

1. Config [Overrides](#overrides)
2. Environmental Variables
    - via [`xcon.providers.environmental.EnvironmentalProvider`](../api/xcon/providers/environmental.html#xcon.providers.environmental.EnvironmentalProvider){target=_blank}.
3. Dynamo flat config cache, Details:
    - [Info About Caching][caching]
    - via [`xcon.providers.dynamo.DynamoCacher`](../api/xcon/dynamo.html#xcon.providers.dynamo.DynamoCacher){target=_blank}
4. AWS Secrets Provider via [`xcon.providers.secrets_manager.SecretsManagerProvider`](../api/xcon/providers/secrets_manager.html#xcon.providers.secrets_manager.SecretsManagerProvider){target=_blank}.
5. AWS SSM Param Store via [`xcon.providers.ssm_param_store.SsmParamStoreProvider`](../api/xcon/providers/ssm_param_store.html#xcon.providers.ssm_param_store.SsmParamStoreProvider){target=_blank}.
6. Config [Defaults](#defaults)

## Standard Directory Paths
[standard-directory-paths]: #standard-directory-paths

Most of the providers have a 'path' you can use with them. I call the path up until just
before the config variable name a directory (see `xcon.directory.Directory`).

If no `Config.SERVICE_NAME` has been provided or is set to `None`
(either from a lack of an environmental variable `SERVICE_NAME`, or via
[override](#overrides) or [default](#defaults)) then we can't use paths that need this value.

At that point, the `Default` Directories searched are these
(see [Directory Chain][directory-chain]; changeable via `Config.directories`):

1. `/global/{APP_ENV}`
2. `/global`

If there is a `Config.SERVICE_NAME` value available, then we will add two extra directories by
`Default` to the [Directory Chain][directory-chain]:

1. `/{APP_NAME}/{APP_ENV}`
2. `/{APP_NAME}/`
3. `/global/{APP_ENV}`
4. `/global/`

If the `Config.APP_ENV` is not configured, it defaults to `dev` at the moment.

As soon as something provides the `APP_ENV` and/or `SERVICE_NAME` to the config by setting
it directly as an override or as a default (or if something changes the app environmental 
variables directly, I dislike doing that for a number of reasons though) it will start 
immediately using the full directory paths, ie: `/{APP_NAME}/{app_env}`, etc.

The [`Config`](../api/xcon/config.html#xcon.config.Config){target=_blank} class is more dynamic... you can think of it as more of a 'view' or 'lens', so
[Configs Are Cheap][configs-are-cheap].

So this "view" and/or "lens" can now be easily changed.  You can do an override like this:

```python
from xcon import config
config.SERVICE_NAME = "someServiceName"
```

Or set a default (if it can't find the value anywhere else):

```python
from xcon import config
config.set_default("service_name", "someServiceName")
```

By default, [overrides] and [defaults] are inherited from the [Parent Chain][parent-chain].

## Exports

???+ note "This is something we have not really utilized yet"
    Config supports it, but we don't really use this feature anywhere currently.

Services/Apps can export values to other apps/services. The standard location for them are:

- `/{OtherApp's-->SERVICE_NAME}/export/{APP_ENV}`

You can add them via `Config.add_export` to let a config object search that export path
last (after all other normal directory paths).


# Details / Reference

Provides the basic [`Config`](../api/xcon/config.html#xcon.config.Config){target=_blank} class, which is used to provide a basic interface to get config values.

## Configs are Cheap
[configs-are-cheap]: #configs-are-cheap

Before we continue, I want to emphasize something. [`Config`](../api/xcon/config.html#xcon.config.Config){target=_blank} is more of a "view" or a "lens" then
something that directly keeps configuration values.  There are a number of resources that
Config uses to get configuration values behind the scenes that the Config objects share.
Because of this Config objects are cheap to create and throw away.

So if you want to change some aspect of Config's
configuration, without effecting the rest of the app by changing the main/default/current
config you can always allocate a Config object anytime you want and just throw it away whenever
you want.

Here is a code example that creates a [`Config`](../api/xcon/config.html#xcon.config.Config){target=_blank} object where the first directory
checked is `/some/dir_path` followed by whatever the Default would normally
be. I then askes it for `SOME_NAME`. It's prefectly fine to do this, the Config object will
still be very fast, as the resources it uses behind the scenes stay allocated and will already
have the value for `SOME_NAME` if it's been asked for previously.

```python
from xcon import Config
from xsentinels import Default
def my_function_is_called_a_lot():
    my_config = Config(directories=[f"/some/dir_path", Default])
    the_value_I_want = my_config.SOME_NAME
```

## Current Config

The Config class is a xinject, `xinject.dependency.Dependency`;
meaning that there is a concept that there is a 'current' or 'default' Config object
that can always be used.

You can get it your self easily anywhere asking [`Config`](../api/xcon/config.html#xcon.config.Config){target=_blank} for it's `.grab()`.

```python
# Import Config class
from xcon import Config

# Ask Config class for the current one.
config = Config.grab()
```

Most of the time, it's more convenient to use a special ActiveResourceProxy object that you can
import and use directly. You can use it as if it's the current config object:

```python
from xcon import config

# Use it as if it's the current/default config object,
# it will proxy what you ask it to the real object
# and return the result:
config.get('SOME_CONFIG_NAME')
```

## Basics

We have a list of `xcon.provider.Provider` that we query, in a priority order.
We also have a list of `xcon.directory.Directory` in priority order as well
(see [Provider Chain][provider-chain] and [Directory Chain][directory-chain]).

For each directory, we ask each provider for
that directories value for a particular config-var name.

You can allocate a new [`Config`](../api/xcon/config.html#xcon.config.Config){target=_blank}() object at any time, and by default [unless you pass
other options into the __init__], it will used a set of shared resources from the
current context. Due to this, creating a Config object is normally very quick.
Especially since the config object will lazily setup most of the internal resources
on demand when it's needed [ie: someone asks for a config var of some sort]. If a previous
Config object was created in the past, most of these resources will already be setup
and be fast to retrieve.

You can use [`Config`](../api/xcon/config.html#xcon.config.Config){target=_blank} as if the config-var is directly on the object:
```python
from xcon import Config
value = Config().SOME_VAR
```

There is also a `DefaultConfig` object that's pre-created and always available at
`config`. You can use it just like a normal Config object; every time
it's used it will lookup the current config object and direct the retrieval to it.

Here is an example:
```python
from xcon import config
value = config.SOME_VAR
```

This is equivalent of doing `Config.current().SOME_VAR`. You can call any method
you want on config that Config supports as well:
```python
from xcon import config
value = config.get("SOME_VAR", "some default value")
```

## Search Order
[search-order]: #search-order

Here is the order we check things in when retrieving a value:

1. [Overrides](#overrides) - Value is set directly on [`Config`](../api/xcon/config.html#xcon.config.Config){target=_blank} or one of Config's parent(s).
    - For more details about parents, see [Parent Chain][parent-chain].
2. [`xcon.providers.environmental.EnvironmentalProvider`](../api/xcon/providers/environmental.html#xcon.providers.environmental.EnvironmentalProvider){target=_blank} first if that provider is
   configured to be used. We don't cache  things from the envirometnal provider, so it's always
   consutled before the cache. See topic [Provider Chain][provider-chain] or the
   `xcon.provider.ProviderChain` class for more details.
3. High-Level flattened cache if it was not disabled (see [Caching][caching]).
4. All other [Providers][provider-chain] / [Directories](#directory-chain)
     - Looked up based first on [Directory Order][directory-chain]
     - Second by [Provider Order][provider-chain].
     - That is, we go though each provider for the first directory; if value still not found
       we go though each provider using the second directory, and so on.
5. [Defaults][defaults] - Finally, if value still has not been found we look at the defaults
    provided to [`Config`](../api/xcon/config.html#xcon.config.Config){target=_blank} or Config's parent (see [Parent Chain][parent-chain]).

### Code Examples

Basic, average/normal example:
```python
from xcon import config

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
from xcon import config

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
from xcon import Config, config

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
from xcon import Config
from xcon.directory import Directory

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
  a `xsentinels.default.Default` value while doing this.We then consult the next parent in the
  To Resole this `Default` value, Config consults the current parent-chain.
  If when reaching the last parent in the chain, we still have a `Default` value,
  sensible/default values are constructed and used.
- While getting a configuration value [`Config`](../api/xcon/config.html#xcon.config.Config){target=_blank} will look for [Overrides][overrides]
  and [Defaults][defaults] in `self` first, and then the parent chain second.

### How it's constructed

If the Config object has their `use_parent == True` (it defaults to True) then it will allow
the parent-chain to grow past it's self in the past/previously activated Config objects.

Config is a xinject Dependency.  Dependency uses a `xinject.context.XContext` object to
keep track of current and past resources.

The parent-chain starts with the current config resource (the one in the current XContext).
If that context has a parent context, we next grab the Config resource from
that parent context and check it's `Config.use_parent`. If `True` we keep doing
this until we reach a Config object without a parent or a `Config.use_parent` 
that is False.

If the `Config.use_parent` is `False` on the Config object that is currently being asked for a
config value:

- If it does not find it's self in the parent-chain (via XContext) then the parent-chain
  will be empty at that moment.  This means it will only consult its self and no other Config object.
  The idea here is the Config object is not a resource in the
  `xinject.context.XContext.parent_chain`
  and so is by its self (ie: alone) and should be isolated in this case.
- If it finds its self, it will allow the parent-chain to grow to the point it finds its
  self in the XContext parent-chain. The purpose of this behavior is  to allow all the 'child'
  config objects to be in the parent-chain. If one of these children has the use_parent=False,
  it will stop at that point and **NOT** have any more child config objects included in the
  parent-chain.
  
  As long as the object is still in the context-hierarchy above that child that had
  use_parent=False it will contain the child objects.


We take out of the chain any config object that is myself. The only objects in
the chain are other Config object instances.

Each config object is consulted until we get an answer that is not a `xsentinels.Default`;
once that is found that is what is used.

Example: If we had two Config object, `A` and `B`. And when `B` was originally constructed,
directory was left at it's `xsentinels.Default` value.

And `A` is the parent of `B` at the time `B` was asked for its directory_chain
(ie: `xcon.config.Config.directory_chain`). This would cause `B` to ask `A` for their
directory_chain because `A` is in `B`'s parent-chain. The directory_chain from `A` is what `B`
would use for it's list of `xcon.directory.Directory`'s to look through when resolving
a configuration value (see `Config.get`).

Here is an example:

```python
from xcon import Config

# This is the current config
A = Config.current()

# We make a new Config, and we DON'T make it 'current'.
# This means it's not tied to or inside any XContext [like `A` above is].
B = Config()

assert B.directory_chain == A.directory_chain

# Import the special config object that always 'acts' like the current config
# which in this case should be `A`.
from xcon import config
assert B.directory_chain == config.directory_chain
```

See [Directory Chain][directory-chain] (later) for what a
`xcon.directory.DirectoryChain` is.

## Provider Chain
[provider-chain]: #provider-chain

[`Config`](../api/xcon/config.html#xcon.config.Config){target=_blank} uses an abstract base class `xcon.provider.Provider` to allow for various
configuration providers. You can see these providers under the `xcon.providers` module.

Each [`Config`](../api/xcon/config.html#xcon.config.Config){target=_blank} class has an ordered list of these providers in the form of a
`xcon.provider.ProviderChain`. This chain is queried when looking for a config value.
Once a value is found, it will be cached by default [if not disabled] via a
[`xcon.providers.dynamo.DynamoCacher`](../api/xcon/dynamo.html#xcon.providers.dynamo.DynamoCacher){target=_blank}.

The dynamo cacher will cache values that are
looked up externally, such as by [`xcon.providers.ssm_param_store.SsmParamStoreProvider`](../api/xcon/providers/ssm_param_store.html#xcon.providers.ssm_param_store.SsmParamStoreProvider){target=_blank},
for example. If we use a provider such as [`xcon.providers.environmental.EnvironmentalProvider`](../api/xcon/providers/environmental.html#xcon.providers.environmental.EnvironmentalProvider){target=_blank},
since this found it locally in a process environmental variable it does not cache it.

The providers are queried in the order they are defined in the `Config.provider_chain`.
If you provide a set of providers as part of creating a `Config.__init__`, the provider_chain
will be in the order the user provided in the \__init__ method.

By `Default`, the `Config.provider_chain` is inherited from the [Parent Chain][parent-chain].

### Supported Providers
    
- [`xcon.providers.environmental.EnvironmentalProvider`](../api/xcon/providers/environmental.html#xcon.providers.environmental.EnvironmentalProvider){target=_blank}
- [`xcon.providers.dynamo.DynamoProvider`](../api/xcon/providers/dynamo.html#xcon.providers.dynamo.DynamoProvider){target=_blank}
- [`xcon.providers.dynamo.DynamoCacher`](../api/xcon/providers/dynamo.html#xcon.providers.dynamo.DynamoCacher){target=_blank}
- [`xcon.providers.ssm_param_store.SsmParamStoreProvider`](../api/xcon/providers/ssm_param_store.html#xcon.providers.ssm_param_store.SsmParamStoreProvider){target=_blank}
- [`xcon.providers.secrets_manager.SecretsManagerProvider`](../api/xcon/providers/secrets_manager.html#xcon.providers.secrets_manager.SecretsManagerProvider){target=_blank}

???+ todo "Need to document how to setup permissions in a serverless project to provide correct"
    access to the specific providers for ssm/dynamo/etc.
    For now, look at [Permissions](#permissions) section for real-works examples of what is needed.

## Directory Chain
[directory-chain]: #directory-chain

Some providers have a path/directory concept, where they have various different sets of config
name/values at a specific path. The path is what we call a specific
`xcon.directory.Directory`. We can get the list of directories that will be queried
via `Config.directory_chain`. It returns a `xcon.directory.DirectoryChain` that has
a list of directories in a specific order.  We search a specific directory on all of our providers
before searching the next directory.

By `Default`, the `Config.directory_chain` is inherited from the [Parent Chain][parent-chain].

For a list of `Default` directories we normally use, and how they would by used to lookup
see [Standard Directory Paths](#standard-directory-paths).

## Caching Details

There are two types of caching in py-xcon:

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

The `xcon.provider.InternalLocalProviderCache` is a resource that is centrally used
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

- When an instance of `InternalLocalProviderCache` is created, it will look for the environmental variable named
  `XCON_INTERNAL_CACHE_EXPIRATION_MINUTES` / [XconSettings.internal_cache_expiration_minutes](../api/xcon/conf.html#xcon.conf.XconSettings.internal_cache_expiration_minutes){target=_blank}.
  If it exists and is true-like it's converted into an `int` and then used as the number of minutes before the cache expires.
- Modifying `xcon.provider.InternalLocalProviderCache.expire_time_delta`.
  You can easily modify it by getting the current resource instance and changing the attribute.
  (via `InternalLocalProviderCache.grab().expire_time_delta`)
      - `expire_time_delta` is a `datetime.timedelta` object. You can use whatever time-units
        you want by allocating a new `timedelta` object.
            - Example: `timedelta(minutes=5, seconds=10)`, for 5 minutes and 10 seconds.

If environmental variable is not set and nothing changes the `expire_time_delta` directly,
it defaults to 15 minutes.

You can always reset the entire cache by calling this method on the current resource instance:
`xcon.provider.InternalLocalProviderCache.reset_cache`.

#### Local Memory Caching Side Notes

There is also an option on `xcon.config.Config.get` that allows you to ignore the local
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
In addition, the [`xcon.providers.dynamo.DynamoCacher`](../api/xcon/dynamo.html#xcon.providers.dynamo.DynamoCacher){target=_blank} generates a random number and
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
`xcon.providers` and `xcon.directory.Directory`'s.

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

???+ todo "Need to document how to setup permissions in a serverless project to provide correct"
    access to the specific cache hash-key for the app. For thoese intrested, look at the
    serverless.yml file in the hubspot repo.

### Disable Default Dynamo Caching

First, let's talk about how to disable caching via environmental variables:

- `XCON_DISABLE_DEFAULT_CACHER`, if 'true':
    - Only by default will the cache will be disabled.
    - This only happens while resolving the `Default` on `xcon.config.Config.cacher`.
    - If you set `DynamoCacher` directly on `xcon.config.Config.cacher` via code,
    caching will still be used regardless.
    - Using this option disables the cacher without having to also disable the providers,
    this means it will still lookup params from SSM and so on, just not use the cached version.
- `XCON_ONLY_ENV_PROVIDER`, if 'true':
    - Regardless of how Config is modified/configured via code, these effects will still happen:
        - The cache will be disabled.
        - The only provider that will be used is the EnvironmentalProvider.
    - See [Disable Cache + Non-Environmental Providers](#disable-cache-non-environmental-providers)



While developing, it's sometimes nice to always grab the values each time you run something
and to NOT cache it. But you only want to do this while running it locally,
you don't want to modify the code it's self to disable caching.

You can set an environmental variable called `XCON_DISABLE_DEFAULT_CACHER` to `True` if you
want to easily disable caching by default.

???+ important "The code will use [`xcon.providers.environmental.EnvironmentalProvider`](../api/xcon/providers/environmental.html#xcon.providers.environmental.EnvironmentalProvider){target=_blank} for this."
    So if you change this environmental variable WHILE in the middle of running the code
    [`xcon.providers.environmental.EnvironmentalProvider`](../api/xcon/providers/environmental.html#xcon.providers.environmental.EnvironmentalProvider){target=_blank} via debugger or other means,
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
regardless of what `XCON_DISABLE_DEFAULT_CACHER` is set too.
The `XCON_DISABLE_DEFAULT_CACHER` will only disable it if `cacher=Default`
(which it does by default).

If you want to permanently disable cacher via code, do the following instead:

{There is an autouse fixture that will disable the cacher during unit tests,
as an example real-world use-case in xcon's pytest_plugin module: `xcon.pytest_plugin.xcon`}

```python
from xcon import Config, config

# Globally/Permanently:
config.cacher = None

# Temporarily via `with`:
from xcon import Config
with Config(cacher=None):
    pass

# Temporarily via decorator:
from xcon import Config
@Config(cacher=None)
def some_method():
    pass
```

### Disable Cache + Non-Environmental Providers

If you set `XCON_ONLY_ENV_PROVIDER` as an actual environmental variable, it will disable
all providers and the cache too.  It needs to be in `os.environ`, so a real environmental variable.

- XCON_ONLY_ENV_PROVIDER: If 'true', by default Config will only use env-variables.
    - If something has specifically set providers, the won't be used while XCON_ONLY_ENV_PROVIDER is on.
    - Cache is also explicitly disabled when XCON_ONLY_ENV_PROVIDER is on, no mater how Config is setup.
  
As a developer, it's nice sometimes to just 'disable' Config, where it only looks at
environmental variables (along any normal overrides/defaults set into it, as it normally would).

The objective with this XCON_ONLY_ENV_PROVIDER is to disable external lookup of any configuration
variables.  Only rely on what is inside the code/process.

This can help with debugging, to see if a problem is due to a coding issue or if it's
some sort of configuration issue.

Or if there is a special process being run that should only use environmental variables.


## Overrides

You can override a value on a [`Config`](../api/xcon/config.html#xcon.config.Config){target=_blank} object in two ways:

1. `Config.set_override`
2. Setting it directly as an attribute, ie:
2. Setting it directly as an attribute, ie:
```
from xcon import config
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
from xcon import config

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

> :warning: todo: Move this into xcon, I think this overview would be better suited there
    since it talks about the other sub-modules, like providers, cacher, etc.

> :warning: todo: Document/implement new cache key scheme where the RANGE key has the
    provider chain + directory chain in it.

## Permissions

By default, if Config gets a permission denied error from a source of configuration,
it will log this but then continue on.

So it should be generally safe to only configure permissions for the path(s) you actually need.
Config will get what it can and use that.

Also, if cacher has an error while trying to retreive values from it, it will log a warning and then not try
again; in general the library only tries to get configuration once and log a single warning if there is an error retrieving it.

This is to make the library resiant and easy to use with it's default settings.

You can adjust the settings via the object at `from xcon import xcon_settings` appropriately,
so it won't attempt to use cache and/or providers that you have not setup permissions for
if you want to remove the warnings.

???+ warning "Config will only log a single warning for each unique permission error."
    If an app does not have permission to a particular directory path on one of the
    provider services in aws; Config will catch that error and log a **warning** the first
    time it encounters that error.  Subsequently, it will remember for that provider + directory
    combination that it had an error and not attempt it again. This is to preserve the performance
    of the system so that it does not get bogged down constantly trying to query inaccessible
    locations. I've tried to limit it to only permission errors and letting other types of
    errors to propagate back to the app [via Exceptions] like you would normally expect.


???+ important "Need to complete this section of documentation"
    I'll complete it soon in the near future, for now you can take a look at
    the `xcon/serverless_files` directory of this project.

    Specifically, look at `xcon-resources.js` for a way to more easily import the files directly from xcon module.
    Or you can copy the files into your own project and modify them as needed.

    For the cache table setup, look at `xcon/serverless_files/config_manager` files.

    You can look at these files and figure it out on your own for now.

    Eventually it WILL be documented.


