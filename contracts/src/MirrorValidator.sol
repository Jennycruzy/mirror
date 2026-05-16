// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract MirrorValidator {
    event ValidationRecorded(bytes32 indexed subject, bytes32 indexed tag, uint256 value);

    function recordValidation(bytes32 subject, bytes32 tag, uint256 value) external {
        emit ValidationRecorded(subject, tag, value);
    }
}

