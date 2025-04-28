# Ignore files under size

plugin for [Unmanic](https://github.com/Unmanic)

# Requirements

To be able to correctly identify movies in radar, this currently uses TMDb id. Therefore this needs to be somewhere in the file name that is being processed. Currently this is found using the following regex: "\{tmdb-(\d+)\}"

E.g.
The Lord of the Rings The Fellowship of the Ring (2001) {tmdb-120} {edition-Extended} [Remux-2160p][DV HDR10][FLAC 7.1][x265]-NAHOM.mkv
