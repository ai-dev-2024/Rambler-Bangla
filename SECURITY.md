# Security policy

## Reporting a problem

Please don't post details of a security problem in a public issue (for
example, a leaked key, a way to make the patch apply to the wrong app build,
or text leaking out of password fields). Open an issue titled "Security
contact request" with no details, and the maintainer will reply with a
private channel.

## Scope

- The patcher, extension source, and CI workflows in this repository.
- Password and other sensitive input fields are meant to pass through
  untouched. Any case where conversion runs in one is a security bug.

This repository distributes no APKs. Builds from elsewhere are out of scope.
