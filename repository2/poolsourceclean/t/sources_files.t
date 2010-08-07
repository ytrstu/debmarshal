#!/usr/bin/perl -w
#
# Test pooldebclean.pl's packages_files()
#
#
# Copyright 2010 Google Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Author: Drake Diedrich <dld@google.com>

use strict;
use Test::More tests => 3;
use File::Temp qw/ tempdir/;
use IO::String;

my $poolsourceclean = './poolsourceclean.pl';

require_ok($poolsourceclean);

my $tempdir =  tempdir( CLEANUP => 1);

is(sources_files($tempdir),0,"no Sources files");

mkdir "$tempdir/sid";
system("touch","$tempdir/README");
system("touch","$tempdir/sid/Sources");
symlink("broken","$tempdir/broken.link");
my @sources = sources_files($tempdir);
is_deeply(\@sources,["$tempdir/sid/Sources"],
	"Sources file");