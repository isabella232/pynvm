import os
import sys
import unittest
import uuid

from nvm import pmemobj


verbose = sys.argv.count('-v') + sys.argv.count('--verbose')
verbose += int(os.environ.get('TEST_VERBOSE', 0))
if verbose > 1:
    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(name)-15s %(levelname)-8s %(message)s')



class TestCase(unittest.TestCase):

    # XXX I'm not sure how one gets a real pmem file, so keep this factored.
    def _test_fn(self):
        fn = "{}.pmem".format(uuid.uuid4())
        self.addCleanup(lambda: os.remove(fn) if os.path.exists(fn) else None)
        return fn


class Test(TestCase):

    def assertMsgBits(self, msg, *bits):
        for bit in bits:
            self.assertIn(bit, msg)

    def test_create_open_close_dont_raise(self):
        fn = self._test_fn()
        pop = pmemobj.create(fn)
        pop.close()
        pop = pmemobj.open(fn)
        pop.close()

    def test_implicit_close_after_create(self):
        fn = self._test_fn()
        pop = pmemobj.create(fn)

    def test_implicit_close_after_open(self):
        fn = self._test_fn()
        pop = pmemobj.create(fn)
        pop.close()
        pop = pmemobj.open(fn)

    def test_small_pool_size_error(self):
        fn = self._test_fn()
        with self.assertRaises(ValueError) as cm:
            pop = pmemobj.create(fn, pmemobj.MIN_POOL_SIZE-1)
        self.assertMsgBits(str(cm.exception),
                           str(pmemobj.MIN_POOL_SIZE-1),
                           str(pmemobj.MIN_POOL_SIZE))

    def test_list_of_strings_as_root_obj(self):
        # Lists and strings are our "built in" types (handled specially by the
        # code because they are used by the type table), so this exercises
        # the absolute minimum required functionality, but doesn't fully
        # exercise anything, including not really testing the type table.
        test_list = ['a', 'b', 'c', 'd']
        fn = self._test_fn()
        pop = pmemobj.create(fn)
        pop.root = pop.new(pmemobj.PersistentList, test_list)
        pop.close()
        pop = pmemobj.open(fn)
        self.assertEqual(pop.root, test_list)


class TestPersistentList(TestCase):

    def _make_list(self, arg):
        self.fn = self._test_fn()
        self.pop = pmemobj.create(self.fn)
        self.pop.root = self.pop.new(pmemobj.PersistentList, arg)
        return self.pop.root

    def _reread_list(self):
        self.pop.close()
        self.pop = pmemobj.open(self.fn)
        return self.pop.root

    def test_insert(self):
        lst = self._make_list([])
        lst.insert(0, 'b')
        self.assertEqual(lst, ['b'])
        lst = self._reread_list()
        self.assertEqual(lst, ['b'])
        lst.insert(-1, 'a')
        self.assertEqual(lst, ['a', 'b'])
        lst = self._reread_list()
        self.assertEqual(lst, ['a', 'b'])
        lst.insert(2, 'c')
        self.assertEqual(lst, ['a', 'b', 'c'])
        lst = self._reread_list()
        self.assertEqual(lst, ['a', 'b', 'c'])
        lst.insert(-10, 'z')
        self.assertEqual(lst, ['z', 'a', 'b', 'c'])
        lst = self._reread_list()
        self.assertEqual(lst, ['z', 'a', 'b', 'c'])
        lst.insert(10, 'y')
        self.assertEqual(lst, ['z', 'a', 'b', 'c', 'y'])
        lst = self._reread_list()
        self.assertEqual(lst, ['z', 'a', 'b', 'c', 'y'])

    def test_repr(self):
        expected = "PersistentList(['a', 'b', 'c'])"
        lst = self._make_list(['a', 'b', 'c'])
        self.assertEqual(repr(lst), expected)
        self.assertEqual(repr(self._reread_list()), expected)

    def test_getitem(self):
        lst = self._make_list(['a', 'b', 'c'])
        self.assertEqual(lst[0], 'a')
        self.assertEqual(lst[1], 'b')
        self.assertEqual(lst[2], 'c')
        lst = self._reread_list()
        self.assertEqual(lst[0], 'a')
        self.assertEqual(lst[1], 'b')
        self.assertEqual(lst[2], 'c')

    def test_getitem_index_errors(self):
        lst = self._make_list(['a', 'b', 'c'])
        with self.assertRaises(IndexError):
            lst[3]
        with self.assertRaises(IndexError):
            lst[-4]
        with self.assertRaises(IndexError):
            lst[10]
        with self.assertRaises(IndexError):
            lst[-10]

    def test_setitem(self):
        lst = self._make_list(['a', 'b', 'c'])
        lst[1] = 'z'
        self.assertEqual(lst, ['a', 'z', 'c'])
        lst = self._reread_list()
        self.assertEqual(lst, ['a', 'z', 'c'])
        lst[-3] = 'y'
        self.assertEqual(lst, ['y', 'z', 'c'])
        lst = self._reread_list()
        self.assertEqual(lst, ['y', 'z', 'c'])

    def test_setitem_index_errors(self):
        lst = self._make_list(['a', 'b', 'c'])
        with self.assertRaises(IndexError):
            lst[3] = 'z'
        with self.assertRaises(IndexError):
            lst[-4] = 'z'
        with self.assertRaises(IndexError):
            lst[10] = 'z'
        with self.assertRaises(IndexError):
            lst[-10] = 'z'

    def test_delitem(self):
        lst = self._make_list(['a', 'b', 'c'])
        del lst[1]
        self.assertEqual(lst, ['a', 'c'])
        lst = self._reread_list()
        self.assertEqual(lst, ['a', 'c'])
        del lst[-2]
        self.assertEqual(lst, ['c'])
        lst = self._reread_list()
        self.assertEqual(lst, ['c'])
        del lst[0]
        self.assertEqual(lst, [])
        lst = self._reread_list()
        self.assertEqual(lst, [])

    def test_delitem_index_errors(self):
        lst = self._make_list(['a', 'b', 'c'])
        with self.assertRaises(IndexError):
            del lst[3]
        with self.assertRaises(IndexError):
            del lst[-4]
        with self.assertRaises(IndexError):
            del lst[10]
        with self.assertRaises(IndexError):
            del lst[-10]

    def test_len(self):
        lst = self._make_list([])
        for i in range(6):
            self.assertEqual(len(lst), i)
            lst = self._reread_list()
            self.assertEqual(len(lst), i)
            lst.append('a')


if __name__ == '__main__':
    unittest.main()