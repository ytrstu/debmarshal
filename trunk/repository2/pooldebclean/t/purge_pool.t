#!/usr/bin/perl -w
#
# Test pooldebclean.pl's purge_pool()
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

my $pooldebclean = './pooldebclean.pl';

require_ok($pooldebclean);

my $tempdir =  tempdir( CLEANUP => 1);

my (%packages,%removed);
sub count_remove {
  my ($filename) = @_;
  $removed{$filename}++;
}

mkdir("$tempdir/pool");
purge_pool("$tempdir/pool","pool",\%packages,\&count_remove);
is_deeply(\%removed, {}, "no Packages files");

system("touch","$tempdir/pool/test.deb");
%removed = ();
purge_pool("$tempdir/pool","pool",\%packages,\&count_remove);
is_deeply(\%removed, { "$tempdir/pool/test.deb" => 1}, "unreferenced deb");

