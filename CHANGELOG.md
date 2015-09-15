# Change Log

## Version: Master

Notable changes since `v0.0-alpha.0`:

1. Drop the ermrest_config.json key for "registry.schema"

 https://github.com/informatics-isi-edu/ermrest/issues/35

1. DELETE /catalog/N doesn't work

 https://github.com/informatics-isi-edu/ermrest/issues/21

1. ACL for catalog creation

 https://github.com/informatics-isi-edu/ermrest/issues/19

 Creating a catalog, by default requires a user with 'admin' role. This ACL can
 be changed by modifying the ACL list in the `ermrest_config.json`
 configuration file.

1. Proposed improvements to 'DELETE /catalog/N'

 https://github.com/informatics-isi-edu/ermrest/issues/14

 See comment on upgrading existing ERMrest `ermrest` databases.

 https://github.com/informatics-isi-edu/ermrest/issues/14#issuecomment-133167668

 This commit also introduces a new utility `ermrest-registry-purge` that
permanently deletes catalogs.
