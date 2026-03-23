from __future__ import annotations

from typing import List


def move_up(options: List[str], index: int) -> List[str]:
	if index <= 0 or index >= len(options):
		return options
	new = options.copy()
	new[index - 1], new[index] = new[index], new[index - 1]
	return new


def move_down(options: List[str], index: int) -> List[str]:
	if index < 0 or index >= len(options) - 1:
		return options
	new = options.copy()
	new[index + 1], new[index] = new[index], new[index + 1]
	return new 