"""
Shader - Compila y gestiona programas GLSL.
"""
from OpenGL.GL import *
import numpy as np


class Shader:
    def __init__(self, vertex_src: str, fragment_src: str):
        self.program = self._create_program(vertex_src, fragment_src)
        self._uniform_cache: dict[str, int] = {}

    def _compile(self, source: str, shader_type) -> int:
        shader = glCreateShader(shader_type)
        glShaderSource(shader, source)
        glCompileShader(shader)
        if not glGetShaderiv(shader, GL_COMPILE_STATUS):
            log = glGetShaderInfoLog(shader).decode()
            kind = "VERTEX" if shader_type == GL_VERTEX_SHADER else "FRAGMENT"
            raise RuntimeError(f"[{kind}] Error compilando shader:\n{log}")
        return shader

    def _create_program(self, vs: str, fs: str) -> int:
        v = self._compile(vs, GL_VERTEX_SHADER)
        f = self._compile(fs, GL_FRAGMENT_SHADER)
        program = glCreateProgram()
        glAttachShader(program, v)
        glAttachShader(program, f)
        glLinkProgram(program)
        if not glGetProgramiv(program, GL_LINK_STATUS):
            log = glGetProgramInfoLog(program).decode()
            raise RuntimeError(f"Error linkeando programa:\n{log}")
        glDeleteShader(v)
        glDeleteShader(f)
        return program

    def use(self) -> None:
        glUseProgram(self.program)

    def _loc(self, name: str) -> int:
        if name not in self._uniform_cache:
            self._uniform_cache[name] = glGetUniformLocation(self.program, name)
        return self._uniform_cache[name]

    def set_mat4(self, name: str, mat: np.ndarray) -> None:
        glUniformMatrix4fv(self._loc(name), 1, GL_FALSE, mat.astype(np.float32))

    def set_vec3(self, name: str, vec) -> None:
        glUniform3f(self._loc(name), float(vec[0]), float(vec[1]), float(vec[2]))

    def set_float(self, name: str, value: float) -> None:
        glUniform1f(self._loc(name), value)

    def set_int(self, name: str, value: int) -> None:
        glUniform1i(self._loc(name), int(value))

    def set_vec2(self, name: str, vec: np.ndarray) -> None:
        glUniform2f(self._loc(name), float(vec[0]), float(vec[1]))

    @classmethod
    def from_files(cls, vert_path: str, frag_path: str) -> "Shader":
        with open(vert_path) as f:
            vs = f.read()
        with open(frag_path) as f:
            fs = f.read()
        return cls(vs, fs)
