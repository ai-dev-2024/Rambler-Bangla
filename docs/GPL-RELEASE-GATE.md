# GPLv3 release gate for the Rambler patch layer

This is a release checklist, not a legal opinion or clearance to distribute
Google's Gboard binaries. Upstream PixelBoard is GPLv3, pinned at commit
`06228a0003a416f04b6a35c3d31530d04032fd6a`; Rambler's repo already
includes `LICENSE` and `ATTRIBUTION.md` and carries GPLv3 notices. The exact
license is `LICENSE` in the upstream repo:
https://github.com/Akshayykadam/PixelBoard/tree/06228a0003a416f04b6a35c3d31530d04032fd6a .

## What must accompany an APK distribution of the covered patch layer

- GPLv3 sections 4 and 5: keep upstream copyright, GPL and warranty notices;
  state prominent changes and relevant dates; license the covered derivative
  as a whole under GPLv3; give recipients the full GPLv3 license; expose
  appropriate legal notices in interactive UI if applicable. An attribution
  page and repository license help but must accurately identify the actual
  modified sources and not imply a proprietary exception.
- Sections 1 and 6: provide machine-readable *Corresponding Source* for the
  exact covered binary offered, with clear directions adjacent to the APK
  download for where to obtain it at no extra charge. Source means preferred
  modification form, not merely decompiled Java or a binary DEX. It includes
  upstream extension Java, generated catalog's XML/generator, Rambler Java,
  the preferred form of new/modified smali hooks and feature implementations,
  relevant resource source, interface definitions, build/patch scripts and
  installation/run instructions needed to reproduce and modify the covered
  part. Pin the exact upstream commit and APK build/patch inputs, script/tool
  versions and hashes. Merely linking the latest Rambler-Bangla main branch
  without all release-specific sources is not enough; tag a release-specific
  source snapshot and offer it for as long as its binary remains offered.
- An unmodified general-purpose compiler, Android SDK or smali tool need not
  be vendored; identify how to obtain it and retain its own license. Don't
  publish signing private keys: GPLv3 does not generally require them for
  an app APK. Section 6 Installation Information can apply to a transaction
  conveying a User Product with a covered executable; assess that separately,
  rather than assuming every download requires private signing material.
- A *closed* personal build/test pipeline need not be published as a system
  diagram or its secrets. But any scripts or transformations actually needed
  to build/install/run/modify the conveyed covered binary are Corresponding
  Source under section 1 and cannot be omitted simply because they live in a
  private pipeline. If part of the pipeline is truly unrelated to the covered
  binary and is a separable general-purpose tool, document that boundary and
  obtain a legal review if uncertain. Do not publish keys, credentials,
  account tokens, private fixture data, or Google proprietary stock binaries.
- A patch-only release that takes a user-supplied Gboard APK avoids bundling
  Google's binary, but still needs the GPL source/notice package for the
  Rambler/PixelBoard-covered patch layer and reproducible instructions. It
  does not itself settle Google's separate terms or the legality of patching.

## Two unresolved release blockers

1. `ATTRIBUTION.md` explicitly says "Do not redistribute patched Gboard APKs"
   because Google's binaries/models/keys are not licensed for redistribution.
   Yet staging APKs have been shared and the requested final artifact is a
   bundled APK. GPLv3 permission for PixelBoard does **not** grant rights in
   Google's proprietary payload. Obtain separate legal clearance or change
   public distribution shape; do not use this note to claim clearance.
2. Much of v32's 38 extra extension descriptors, and possibly modified shared
   extension and stock host methods, currently exists only in a signed DEX or
   smali dumps. If it becomes part of a distributed final build, complete its
   preferred editable source and relevant build transforms before claiming
   GPL Corresponding Source availability. The pinned upstream/v32 descriptor
   comparison yielded 232 shared and 38 extra extension descriptors, but the
   exact descriptor lists are not part of this docs-and-tests branch. Descriptor
   equality is not proof of source completeness or build reproducibility.

Practical gate: before production distribution, audit the exact final APK,
match every covered code/resource change to its preferred source and script,
confirm source download directions alongside its download link, check notices
and license in the resulting app and source, and resolve the separate Google
binary-rights issue with counsel or a different delivery plan. The local r34 staging shell is not a final production release; this
docs-and-tests branch omits its build script and shell source.
