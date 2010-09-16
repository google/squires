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
    return ['pissweak', 'weak', 'strong', 'superman']

  def Set(self, command, unused_command):
    colour = command.GetOption('colour')
    filename = command.GetOption('file')
    pager = command.GetOption('pager')
    strength = command.GetOption('strength')

    print 'Colour is: %s' % colour
    print 'File is: %s' % filename
    print 'Pager is: %s' % pager
    print 'Strength is: %s' % strength

  def Look(self, command, unused_command):
    direction = command.GetOption('<direction>')
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


class CmdRoot(squires.Command):
  """The root of the command tree."""

  def Run(self, unused_command):
    # Override the Run() method to prevent a blank
    # line from generating an 'incomplete line' message.
    pass


def main(unused_argv):
  # First create the root of the tree
  cmd_tree = CmdRoot()
  # Mandatory to initialise the readline environment.
  cmd_tree.PrepareReadline()

  cmd_tree.name = '<root>'
  cmd_tree.prompt = 'adventure> '

  adventure = Adventure()

  use = cmd_tree.AddCommand('use', help='Use an item.')
  weapon = use.AddSubCommand('weapon', help='Use a weapon.', runnable=True,
                             method=adventure.UseWeapon)
  weapon.AddOption('<item>', group='item', helptext='Weapon to use',
                   required=True, boolean=False,
                   match=adventure.GetInventory)

  food = use.AddSubCommand('food', help='Eat some food..', runnable=True,
                           method=adventure.UseFood)
  food.AddOption('<item>', group='item', helptext='Food to eat', required=True,
                 boolean=False, match=adventure.GetInventory)

  pickup = cmd_tree.AddCommand('pickup', help='Pick up an item',
                               runnable=True,
                               method=adventure.Pickup)
  pickup.AddOption('<item>', helptext='Item to pick up', group='items',
                   boolean=False, match='\w', required=True)
  pickup.AddOption('chupachups', group='items', boolean=False, required=True)

  set = cmd_tree.AddCommand('set', help='Set something', runnable=True,
                            method=adventure.Set)
  set.AddOption('colour', helptext='Cli colour', match='[a-z]+',
                keyvalue=True, default='white')
  set.AddOption('file', helptext='Dump gold to file', is_path=True, keyvalue=True
                    )
  set.AddOption('pager', helptext='Change screen pager', keyvalue=True,
                match={'on': 'Set pager on', 'off': 'Disable the pager'})
  set.AddOption('linewrap', helptext='Change line wrap', keyvalue=True,
                match={'on': 'Set linewrap on', 'off': 'Disable linewrap'})
  set.AddOption('strength', helptext='Set strength', keyvalue=True,
                match=adventure.GetStrengths, hidden=True)

  look = cmd_tree.AddCommand('look', help='Take a look around the room',
                             runnable=True, method=adventure.Look)
  look.AddOption('<direction>', helptext='Look a specific direction',
                 boolean=False, match='\w')

  walk = cmd_tree.AddCommand('walk', help='Walk somewhere',
                              method=adventure.Walk)
  walk.AddOption('direction', helptext='Direction to walk',
                 match=('north', 'south', 'east', 'west'),
                 default='north')

  cmd_tree.AddCommand('inventory', help='See your inventory', runnable=True,
                      method=adventure.Inventory)


  adventure.SlowPrint('Welcome to Squires Adventure 1.0! Press <tab> for help.')

  cmd_tree.Loop()


if __name__ == '__main__':
  main(None)
