#!/usr/bin/python
#
# Copyright 2010 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Simple example script for Squires.

This script gives a simple example (in the form of a useless
text adventure game) for how to build a Squires based interface.
"""

import random
import sys
import time

import squires


class Adventure(object):
  """A simple class for a super-dumb adventure game."""

  def __init__(self):
    # Set initial player inventory.
    self.inventory = {
        'dagger': 1,
        'chupachup': 2,
    }

  def GetInventory(self, *args):
    return self.inventory.keys()

  def SlowPrint(self, line):
    """Prints the supplied line slowly (Ancient modem style).

    A hash (#) in the line causes a 1s pause (and is not printed).

    Args:
      line: A string, the line to print.
    """
    for char in line:
      if char == '#':
        time.sleep(1)
        continue
      sys.stdout.write(char)
      sys.stdout.flush()
      time.sleep(0.01)
    sys.stdout.write('\n')

  def UseWeapon(self, command, unused_command):
    item = command.GetGroupOption('item')
    if item in self.inventory:
      self.SlowPrint('You attempt to use a %s as a weapon.' % item)
      self.SlowPrint('There is nothing here to attack.')
    else:
      self.SlowPrint('You dont have a %s to attack with!' % item)

  def UseFood(self, command, unused_command):
    item = command.GetGroupOption('item')
    if item in self.inventory and self.inventory[item] > 0:
      self.SlowPrint('You attempt to eat a %s.' % item)
      time.sleep(1)
      if item == 'chupachup':
        self.inventory['chupachup'] -= 1
        time.sleep(1)
        self.SlowPrint('*suck suck suck*')
        time.sleep(1)
        self.SlowPrint('Yum!')
      else:
        self.SlowPrint('You are not a trained sword swallower. ')
        time.sleep(1)
        self.SlowPrint('You die from internal bleeding.')
        time.sleep(1)
        raise EOFError
    else:
      self.SlowPrint('You dont have a %s to eat!' % item)

  def Pickup(self, command, unused_command):
    item = command.GetGroupOption('items')
    if item == 'chupachups':
      self.SlowPrint('You picked up the chupachups.')
      self.inventory['chupachup'] += 1
    else:
      self.SlowPrint('I dont see a %s.' % item)

  def GetStrengths(self, unused_arg):
    return {
        'pissweak': 'Pointless!',
        'weak': 'Meh',
        'strong': 'Better',
        'superman': 'Now we\'re talking!'
        }

  def Set(self, command, unused_command):
    colour = command.GetOption('colour')
    filename = command.GetOption('file')
    pager = command.GetOption('pager')
    strength = command.GetOption('strength')

    if command.GetOption('error'):
      raise Exception('boo!')

    print 'Colour is: %s' % colour
    print 'File is: %s' % filename
    print 'Pager is: %s' % pager
    print 'Strength is: %s' % strength

  def Look(self, command, unused_command):
    direction = command.GetOption('direction')
    if direction is None:
      self.SlowPrint('You see various things in different places.# Look where?')
    elif direction in ('north', 'south', 'east', 'west'):
      self.SlowPrint('You see a corridor to the %s' % direction)
    elif direction == 'up':
      self.SlowPrint('There is a wet stone ceiling above your head.')
    elif direction == 'down':
      self.SlowPrint('You see Chupa Chups on the floor.# Looks tasty.')
    else:
      self.SlowPrint('I dont know how to look %s' % direction)

  def Walk(self, command, _):
    direction = command.GetOption('direction')
    print 'Walking %s' % direction
    if not random.randint(0, 7):
      self.SlowPrint('You are eaten by a grue.')
      time.sleep(1)
      raise EOFError
    if direction == 'east' or direction == 'west':
      self.SlowPrint('You walk down a long corridor.')
    else:
      self.SlowPrint('You have entered a room with four exits.')

  def Inventory(self, command, unused_command):
    self.SlowPrint('Current inventory items:')
    for item, count in self.inventory.iteritems():
      self.SlowPrint('%d# %s(s)' % (count, item))

  def Fight(self, command, unused_command):
    self.SlowPrint('Fighting %s with a %s...' % (
        command.GetOption('enemy'),
        command.GetOption('weapon')))

  def Say(self, command, unused_command):
    if command.GetOption('shout'):
      tone = 'shout'
    else:
      tone = 'mutter'
    self.SlowPrint('You %s, "%s".' % (tone, command.GetOption('words')))


class CmdRoot(squires.Command):
  """The root of the command tree."""

  def Run(self, unused_command):
    # Override the Run() method to prevent a blank
    # line from generating an 'incomplete line' message.
    pass


def main(unused_argv):
  # First create the root of the tree
  cmd_tree = CmdRoot()

  cmd_tree.name = '<root>'
  cmd_tree.prompt = 'adventure> '

  adventure = Adventure()

  COMMAND, OPTION, PIPETREE, PIPE = squires.Definitions()

  tree = {
      PIPETREE(tree=squires.DEFAULT_PIPETREE): {},
      COMMAND('use', help='Use an item'): {
          COMMAND('weapon', help='Use a weapon', method=adventure.UseWeapon): (
              OPTION('item', helptext='Weapon to use', group='item',
                     required=True, match=adventure.GetInventory),
              ),
          COMMAND('food', help='Eat some food', method=adventure.UseFood): (
              OPTION('item', helptext='Food to eat.', group='item',
                     required=True, match=adventure.GetInventory
                    ),
              ),
          },
      COMMAND('pickup', help='Pickup an item.', method=adventure.Pickup): (
          OPTION('item', helptext='Item to pickup.', group='items',
                 required=True, match='\w+'),
          OPTION('chupachups', group='items', required=True),
          ),
      COMMAND('set', help='Set something.', method=adventure.Set): (
          OPTION('colour', helptext='Cli colour', match='[a-z]+',
                 keyvalue=True, default='white'),
          OPTION('error', helptext='Make an error', boolean=True),
          OPTION('file', helptext='Dump gold ot file', is_path=True,
                 keyvalue=True, default='default.txt'),
          OPTION('pager', helptext='Change screen pager', keyvalue=True,
                 match={'on': 'Enable the pager', 'off': 'Disable the pager'}),
          OPTION('power', helptext='Change power', keyvalue=True,
                 match={'low': 'Set power low', 'high': 'Set power high'}),
          OPTION('linewrap', helptext='Change linewrap', keyvalue=True,
                 match={'on': 'Set linewrap on', 'off': 'Set linewrap off'}),
          OPTION('strength', helptext='Set strength', keyvalue=True,
                 match=adventure.GetStrengths, hidden=True, default='strong'),
          ),
      COMMAND('look', help='Look around the room', method=adventure.Look): (
          OPTION('direction', helptext='Direction to look',
                 boolean=False, match='\w+', default='up'),
          ),
      COMMAND('fight', help='Fight an enemy', method=adventure.Fight): (
          OPTION('enemy', helptext='Enemy to fight', boolean=False,
                 keyvalue=True, match='\S+'),
          OPTION('weapon', helptext='Weapon to use', boolean=False,
                 keyvalue=False, match='\S+'),
          ),
      COMMAND('walk', help='Walk somewhere', method=adventure.Walk): (
          OPTION('direction', helptext='Direction to walk',
                 match=('north', 'northeast', 'south', 'east', 'west'),
                 default='north'),
          ),
      COMMAND('inventory', help='See your inventory',
              method=adventure.Inventory): {},
      COMMAND('say', help='Say something', method=adventure.Say): (
          OPTION('shout', helptext='Shout it out!'),
          OPTION('words', helptext='Words to say', keyvalue=True,
                 boolean=False, match='.+', multiword=True),
          ),
  }

  squires.ParseTree(cmd_tree, tree)
  adventure.SlowPrint('Welcome to Squires Adventure 1.0! Press <tab> for help.')

  cmd_tree.Loop()


if __name__ == '__main__':
  main(None)
